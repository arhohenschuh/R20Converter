"""Read R20Exporter's captured compendium pages without treating them as game mechanics."""

import hashlib
import html
import json
import os
import re
import stat
import zipfile
from collections import OrderedDict
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup

from entities.base import DatabaseFile, Entity, isRoll20Placeholder
from entities.journal import Handout


def _require(condition, message):
    if not condition:
        raise ValueError("Compendium export: " + message)


class CompendiumExport(object):
    MAX_TOTAL_BYTES = 544 * 1024 * 1024
    MAX_MEMBER_BYTES = 32 * 1024 * 1024
    MAX_METADATA_BYTES = 16 * 1024 * 1024
    PAGE_FILES = {"pagecontent.html": "contentHtml", "pageattrs.html": "attributesHtml",
                  "illustrations.html": "illustrationsHtml", "attributes.json": "attributes"}
    HTML_TAGS = frozenset(("a", "abbr", "b", "blockquote", "br", "caption", "cite", "code", "col", "colgroup",
                          "dd", "del", "details", "dfn", "div", "dl", "dt", "em", "figcaption", "figure",
                          "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "kbd", "li",
                          "ol", "p", "pre", "s", "section", "small", "span", "strong", "sub", "summary", "sup",
                          "table", "tbody", "td", "th", "thead", "tfoot", "tr", "u", "ul"))

    def __init__(self, path):
        self.source = {}
        self.pages = []
        self.assets = []
        self.path = path
        try:
            with zipfile.ZipFile(path) as archive:
                self._load(archive)
        except (OSError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, KeyError) as error:
            raise ValueError("Compendium export: cannot read archive (%s)" % error) from error
        self._pages_by_url = {self.page_identity(page["requestUrl"], self.source["expansion"]): page
                              for page in self.pages}
        self._installed = False

    @staticmethod
    def _seed(value):
        return "r20compendium-" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _handout_id(self, page):
        identity = self.page_identity(page["requestUrl"], self.source["expansion"])
        return self._seed(json.dumps(identity, ensure_ascii=True))

    def _page_id(self, page):
        return Entity.normalizeID(self._handout_id(page) + "-text")

    def _link_target(self, value, converter, base_url=None):
        if not base_url and "/compendium/" not in value:
            return None
        address = urlsplit(urljoin(base_url or self.source["indexUrl"], value))
        if address.scheme not in ("http", "https") or address.netloc not in ("app.roll20.net", "roll20.net", "www.roll20.net"):
            return None
        try:
            identity = self.page_identity(address._replace(scheme="https", netloc="app.roll20.net").geturl(),
                                          self.source["expansion"])
        except ValueError:
            return None
        page = self._pages_by_url.get(identity)
        if page is None:
            return None
        target = "JournalEntry.%s.JournalEntryPage.%s" % (Entity.normalizeID(self._handout_id(page)), self._page_id(page))
        if converter.getArgument("export_as_module", False):
            target = "Compendium.%s.journal.%s" % (converter.name, target)
        if address.fragment:
            fragment = unquote(address.fragment)
            if not re.search(r"[\[\]{}\s]", fragment):
                target += "#" + fragment
        return target

    def _rewrite_anchors(self, document, converter, base_url=None):
        for anchor in document.find_all("a", href=True):
            target = self._link_target(anchor["href"], converter, base_url)
            if target:
                label = re.sub(r"[\[\]{}]", "_", anchor.get_text(" ", strip=True)) or "Reference"
                anchor.replace_with(document.new_string("@UUID[%s]{%s}" % (target, label)))
            elif base_url and not anchor["href"].startswith("#"):
                anchor["href"] = urljoin(base_url, anchor["href"])

    def rewrite_links(self, content, converter):
        if "/compendium/" not in content:
            return content
        document = BeautifulSoup(content, "html.parser")
        self._rewrite_anchors(document, converter)
        return str(document)

    @staticmethod
    def _html_attribute(tag, name, value):
        if name == "href":
            return tag == "a" and urlsplit(value).scheme in ("", "http", "https", "mailto")
        if name in ("id", "class", "title", "lang", "dir", "style"):
            return True
        return name in {"img": ("src", "alt", "width", "height"), "th": ("colspan", "rowspan", "scope"),
                        "td": ("colspan", "rowspan"), "col": ("span", "width"), "colgroup": ("span",),
                        "ol": ("start", "type", "reversed"), "li": ("value",), "details": ("open",)}.get(tag, ())

    def _render_page(self, page, converter, asset_paths):
        document = BeautifulSoup("\n".join(page[field] for field in
                                 ("contentHtml", "attributesHtml", "illustrationsHtml")), "html.parser")
        for element in document.find_all(("script", "style", "iframe", "object", "embed", "form", "base", "link", "meta")):
            element.decompose()
        for element in document.find_all(("img", "source", "video", "audio")):
            _require(element.name == "img" and not element.has_attr("srcset"), "unsupported media in captured page")
            value = element.get("src", "")
            if value.startswith("data:"):
                _require(re.match(r"^data:image/(?:png|jpeg|gif|webp);base64,[A-Za-z0-9+/=\s]+$", value), "unsupported embedded image")
                continue
            address = urlsplit(urljoin(page["responseUrl"], html.unescape(value)))._replace(fragment="").geturl()
            _require(address in asset_paths, "image is not bundled: %s" % address)
            element["src"] = asset_paths[address]
        self._rewrite_anchors(document, converter, page["responseUrl"])
        return bleach.clean(str(document), tags=self.HTML_TAGS, attributes=self._html_attribute,
                            protocols=("http", "https", "mailto", "data"), strip=True,
                            css_sanitizer=CSSSanitizer())

    def install(self, converter):
        _require(not self._installed, "already installed")
        database = DatabaseFile(converter, "compendium-reference.db")
        helper = Entity.__new__(Entity)
        helper._database = database
        helper._converter = converter
        asset_paths = {}
        for asset in self.assets:
            _require(not isRoll20Placeholder(asset["content"]), "placeholder image in archive")
            _filename, asset_paths[asset["url"]] = helper._storeAssetContent(
                asset["url"], os.path.join("assets", "compendium", asset["path"].rsplit("/", 1)[-1]),
                asset["content"], type="compendium", dedup=True)
        root_id = self._seed("folder:" + self.source["indexUrl"] + ":" + self.source["expansion"])
        root_name = self.source["title"].strip() + " (Compendium)"
        folder = {"id": root_id, "n": root_name, "i": []}
        categories = OrderedDict()
        handouts = []
        for page in self.pages:
            parent = root_id
            if page["kind"] != "index":
                category = next((link.get("category", "").strip() for link in page["links"]
                                 if link.get("category", "").strip()), "Entries")
                if category not in categories:
                    categories[category] = {"id": self._seed(root_id + ":" + category), "n": category, "i": []}
                    folder["i"].append(categories[category])
                parent = categories[category]["id"]
                children = categories[category]["i"]
            else:
                children = folder["i"]
            handout = {"id": self._handout_id(page), "name": page["title"], "notes": self._render_page(page, converter, asset_paths),
                       "gmnotes": "", "avatar": "", "archived": False, "inplayerjournals": [], "controlledby": [],
                       "r20_compendium": {"sourceUrl": page["requestUrl"], "pageId": page["pageId"],
                           "expansion": self.source["expansion"], "book": self.source["title"],
                           "captureScope": "selected-index-and-direct-links"},
                       "r20_compendium_page_id": self._page_id(page)}
            children.append(handout["id"])
            handouts.append((handout, parent, len(children) - 1))
        existing = {Entity.normalizeID(handout["id"]) for handout in converter.campaign["handouts"]}
        _require(not existing.intersection(Entity.normalizeID(handout["id"]) for handout, _parent, _index in handouts),
                 "reference Journal ID collides with campaign content")
        converter.campaign["handouts"].extend(handout for handout, _parent, _index in handouts)
        converter.campaign["journalfolder"].append(folder)
        root_folder = converter.folders.addFolder("handout" + root_id, root_name, "JournalEntry", None)
        root_folder.entity["sort"] = len(converter.campaign["journalfolder"]) * Entity.SORT_ORDER
        for index, category in enumerate(categories.values()):
            created = converter.folders.addFolder("handout" + category["id"], category["n"], "JournalEntry", "handout" + root_id)
            created.entity["sort"] = (index + 1) * Entity.SORT_ORDER
        for handout, parent, index in handouts:
            converter.journal.entities.append(Handout(converter.journal, handout, index, "handout" + parent, "compendium"))
        self._installed = True
        converter.logInfo("Compendium converted: %s; %d reference journals and %d bundled images (captured index scope)." %
                          (self.source["title"], len(handouts), len(self.assets)))

    @staticmethod
    def _safe_path(name):
        _require(isinstance(name, str) and name and "\\" not in name and ":" not in name
                 and not name.startswith("/") and not any(part in ("", ".", "..")
                     for part in name.rstrip("/").split("/")), "unsafe ZIP member path")

    @staticmethod
    def page_identity(url, expansion):
        _require(isinstance(url, str), "invalid page URL")
        address = urlsplit(url)
        _require(address.scheme == "https" and address.hostname == "app.roll20.net"
                 and address.netloc == "app.roll20.net"
                 and address.path.startswith("/compendium/dnd5e/"), "unsupported page origin or game system")
        query = parse_qs(address.query, keep_blank_values=True)
        _require(set(query).issubset({"expansion"}) and query.get("expansion", [expansion]) == [expansion],
                 "page belongs to a different expansion")
        return tuple(unquote(segment) for segment in address.path.split("/")), expansion

    def _load(self, archive):
        entries = archive.infolist()
        _require(0 < len(entries) <= 30000, "invalid ZIP member count")
        _require(sum(entry.file_size for entry in entries) <= self.MAX_TOTAL_BYTES, "archive exceeds size limit")
        seen = set()
        for entry in entries:
            self._safe_path(entry.filename)
            _require(entry.filename.casefold() not in seen, "duplicate ZIP member: %s" % entry.filename)
            seen.add(entry.filename.casefold())
            _require(not stat.S_ISLNK(entry.external_attr >> 16), "symbolic ZIP members are unsupported")
            _require(entry.file_size <= self.MAX_MEMBER_BYTES, "ZIP member exceeds size limit")
        manifest = self._json(archive, "compendium.json")
        report = self._json(archive, "export_report.json")
        _require(isinstance(manifest, dict) and isinstance(report, dict), "manifest and report must be objects")
        _require(manifest.get("R20Compendium_format") == "1.0", "unsupported format; expected R20Compendium 1.0")
        _require(manifest.get("capture_format") == "dom-serialized-html-and-ordered-attributes"
                 and manifest.get("scope") == "selected-index-and-direct-links", "unsupported capture format or scope")
        _require(report.get("format_version") == "1.0" and report.get("status") == "complete-within-index"
                 and not report.get("issues") and not report.get("failures"),
                 "capture is incomplete; provide a complete compendium ZIP")
        source = manifest.get("source")
        _require(isinstance(source, dict) and report.get("source") == source, "source identity mismatch")
        _require(isinstance(source.get("title"), str) and source["title"].strip(), "missing book title")
        expansion = source.get("expansion")
        _require(isinstance(expansion, str) and re.fullmatch(r"\d+", expansion), "missing expansion identity")
        index_identity = self.page_identity(source.get("indexUrl"), expansion)
        _require(report.get("scope") == manifest["scope"]
                 and report.get("exporter_version") == manifest.get("exporter_version"), "capture metadata mismatch")
        self.source = dict(source)
        self.exporter_version = manifest.get("exporter_version")
        referenced = {"compendium.json", "export_report.json"}
        contents = {}
        pages = manifest.get("pages")
        _require(isinstance(pages, list) and 1 < len(pages) <= 2000, "invalid page population")
        identities = set()
        for position, page in enumerate(pages):
            _require(isinstance(page, dict) and page.get("outcome") == "captured", "uncaptured page")
            _require(page.get("kind") == ("index" if position == 0 else "entry"), "invalid page order")
            identity = self.page_identity(page.get("requestUrl"), expansion)
            _require(identity not in identities, "duplicate page identity")
            identities.add(identity)
            _require(self.page_identity(page.get("responseUrl"), expansion) == identity
                     and page.get("expansion") == expansion, "response identity mismatch")
            _require(isinstance(page.get("pageId"), str) and re.fullmatch(r"\d+", page["pageId"])
                     and isinstance(page.get("title"), str) and page["title"].strip(), "missing page identity or title")
            if position == 0:
                _require(identity == index_identity and page["pageId"] == source.get("pageId"), "book index mismatch")
            links = page.get("links")
            _require(isinstance(links, list) and all(isinstance(link, dict)
                and all(isinstance(link.get(field, ""), str) for field in ("href", "label", "category"))
                for link in links), "invalid index links")
            descriptors = page.get("files")
            _require(isinstance(descriptors, list) and len(descriptors) == len(self.PAGE_FILES), "missing page fragments")
            loaded = dict(page)
            fragments = set()
            for descriptor in descriptors:
                content = self._member(archive, descriptor, referenced, contents)
                filename = descriptor["path"].rsplit("/", 1)[-1]
                _require(descriptor["path"].startswith("pages/" + page["pageId"] + "-")
                         and filename in self.PAGE_FILES and filename not in fragments, "invalid page fragment")
                fragments.add(filename)
                text = content.decode("utf-8")
                loaded[self.PAGE_FILES[filename]] = json.loads(text) if filename == "attributes.json" else text
            attributes = loaded["attributes"]
            _require(isinstance(attributes, list) and len(attributes) == page.get("attributeCount")
                     and all(isinstance(attribute, dict) and all(isinstance(attribute.get(field), str)
                         for field in ("name", "value", "html")) for attribute in attributes), "invalid ordered attributes")
            self.pages.append(loaded)
        assets = manifest.get("assets")
        _require(isinstance(assets, list), "invalid assets")
        asset_counts = {"planned": len(assets), "bundled": 0, "embedded": 0, "failed": 0, "unsupported": 0, "cancelled": 0}
        urls = set()
        for asset in assets:
            _require(isinstance(asset, dict) and asset.get("outcome") in ("bundled", "embedded"), "uncaptured asset")
            asset_counts[asset["outcome"]] += 1
            if asset["outcome"] == "embedded":
                continue
            url = asset.get("url")
            _require(isinstance(url, str) and url not in urls and urlsplit(url).scheme in ("http", "https"), "invalid asset URL")
            urls.add(url)
            content = self._member(archive, asset, referenced, contents)
            _require(asset["path"].startswith("assets/") and len(content) > 0, "missing asset body")
            self.assets.append(dict(asset, content=content))
        _require(report.get("pages") == {"planned": len(pages), "captured": len(pages), "failed": 0, "cancelled": 0}
                 and report.get("assets") == asset_counts, "report population mismatch")
        _require({entry.filename for entry in entries if not entry.is_dir()} == referenced, "unlisted ZIP members")

    def _json(self, archive, name):
        _require(archive.getinfo(name).file_size <= self.MAX_METADATA_BYTES, "metadata exceeds size limit")
        return json.loads(archive.read(name).decode("utf-8"))

    def _member(self, archive, descriptor, referenced, contents):
        _require(isinstance(descriptor, dict), "invalid file descriptor")
        name = descriptor.get("path")
        self._safe_path(name)
        _require(name not in ("compendium.json", "export_report.json"), "invalid payload path")
        size = descriptor.get("bytes")
        checksum = descriptor.get("sha256")
        _require(type(size) is int and size >= 0 and isinstance(checksum, str)
                 and re.fullmatch(r"[a-fA-F0-9]{64}", checksum), "invalid file identity")
        _require(archive.getinfo(name).file_size == size, "size mismatch: %s" % name)
        if name not in contents:
            contents[name] = archive.read(name)
        content = contents[name]
        _require(hashlib.sha256(content).hexdigest() == checksum.lower(), "hash mismatch: %s" % name)
        referenced.add(name)
        return content