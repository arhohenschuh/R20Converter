import json
import re
from .base import DatabaseFile, Entity
from .users import User
from .rolltemplates import RollTemplate

class ChatLog(DatabaseFile):
    def __init__(self, converter):
        DatabaseFile.__init__(self, converter, "messages.db")
        self._archive = self._campaign.get("chat_archive", [])
        self.entities = self.genEntities()

    def genEntities(self):
        messages = []
        for msg_group in self._archive:
            if not isinstance(msg_group, dict):
                continue
            for msg_id in msg_group.keys():
                try:
                    messages.append(ChatMessage(self, msg_id, msg_group[msg_id]))
                except Exception as e:
                    self.logWarning("Error converting Chat message : %s" % str(e))
        return messages

class ChatMessage(Entity):
    TYPE_OTHER = 0
    TYPE_OOC = 1
    TYPE_IC = 2
    TYPE_EMOTE = 3
    TYPE_WHISPER = 4
    TYPE_ROLL = 5
    def __init__(self, database, id, message):
        Entity.__init__(self, database, id)
        roll_type = ChatMessage.TYPE_OOC
        whispers = []
        content = message["content"].encode('latin-1').decode()
        who = message["who"].encode('latin-1').decode()
        sound = None
        roll = None
        inline = list(map(lambda r: Roll(r["expression"].encode('latin-1').decode(), r["results"]), message.get("inlinerolls", [])))
        hidden_gm_whisper = message["type"] == "hidden" \
            and message.get("original_type") == "whisper" \
            and message.get("target") == "gm"
        secret_roll_result = message["type"] == "secretrollresult" \
            and message.get("secret") is True

        if message["type"] == "whisper" or hidden_gm_whisper:
            if message["target"] == "gm":
                whispers = self.getGMWhispers()
            else:
                whispers.append(Entity.normalizeID(message["target"]))
            roll_type = ChatMessage.TYPE_WHISPER
        elif message["type"] == "emote":
            roll_type = ChatMessage.TYPE_EMOTE
        elif message["type"] == "rollresult" or message["type"] == "gmrollresult":
            roll_type = ChatMessage.TYPE_ROLL
            sound = "sounds/dice.wav"
            r20roll = json.loads(content)
            content = message["origRoll"].encode('latin-1').decode()
            roll = Roll(content, r20roll)
            if message["type"] == "gmrollresult":
                whispers = self.getGMWhispers()
        elif secret_roll_result:
            whispers = self.getGMWhispers()

        if "rolltemplate" in message:
            content = RollTemplate(message["rolltemplate"], content, inline).toHTML()
        elif message["type"] in ["whisper", "emote", "general"]:
            content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;").replace("\'", "&#039;")
        content = self._replaceInlineRolls(content, inline)
        content = self._replaceLinks(content)
        self.entity = {
            "_id": self._id,
            "flags": {},
            "type": roll_type,
            "user": Entity.normalizeID(message["playerid"]),
            "timestamp": message[".priority"],
            "content": content,
            "speaker": {"alias": who},
            "whisper": whispers,
        } 
        if sound:
            self.entity["sound"] = sound
        if roll:
            # v10 replaced the single ChatMessage#roll string with a `rolls`
            # array; the migration was dropped in 12.316 (ADR-002).
            self.entity["rolls"] = [roll.toJSON()]

    def getGMWhispers(self):
        whispers = []
        for i in self._converter.users.entities:
            if i.entity["role"] == User.ROLE_GM:
                whispers.append(i._id)
        return whispers

    def _replaceInlineRolls(self, content, rolls):
        def repl(match):
            idx = int(match.group(1))
            if idx < 0 or idx >= len(rolls):
                return match.group(0)
            return rolls[idx].getInline()
        return re.sub(r'\$\[\[(\d+)\]\]', repl, content)

    def _replaceLinks(self, content):
        def repl(match):
            return "<a href=\"{}\">{}</a>".format(match.group(2).replace('&', '&amp;').replace('\"', '&quot;'), match.group(1))
        return re.sub(r'\[(.+?)\]\((.*?)\)', repl, content, flags=re.DOTALL)

class Roll:
    def __init__(self, formula, r20roll):
        self.formula = formula
        self.total = r20roll["total"]
        self.parts = []
        for roll in r20roll["rolls"]:
            if roll["type"] == "R":
                dice = {
                    'class': 'Die',
                    'number': roll["dice"],
                    'faces': roll["sides"],
                    "formula": "{}d{}".format(roll["dice"], roll["sides"]),
                    "options": {},
                    "rolls": []
                }
                for result in roll.get("results", []):
                    die = {"roll": result["v"]}
                    if result.get("d", False):
                        die["discarded"] = True
                    dice["rolls"].append(die)
                self.parts.append(dice)
            elif roll["type"] == "G":
                # Compound rolls, like {1d20, 1d20} or {1d20, 1d20}kh1
                # FIXME: Ignoring the 'rolls' attribute which contains the actual rolls.
                dice = {
                    'class': 'Die',
                    'number': len(roll.get("results", [])),
                    'faces': 0,
                    "formula": "0d0",
                    "options": {},
                    "rolls": []
                }
                for result in roll.get("results", []):
                    die = {"roll": result["v"]}
                    if result.get("d", False):
                        die["discarded"] = True
                    dice["rolls"].append(die)
                self.parts.append(dice)
            elif roll["type"] == "M":
                self.parts.append(str(roll["expr"]))
            elif roll["type"] == "L" or roll["type"] == "C":
                pass # text
            else:
                raise Exception("Unknown roll type %s" % str(roll))

    def isCrit(self):
        for part in self.parts:
            if isinstance(part, dict):
                for roll in part["rolls"]:
                    if roll.get("discarded", False):
                        continue
                    if roll["roll"] == part["faces"]:
                        return True
                        
    def isFail(self):
        for part in self.parts:
            if isinstance(part, dict):
                for roll in part["rolls"]:
                    if roll.get("discarded", False):
                        continue
                    if roll["roll"] == 1:
                        return True

    def getTooltip(self):
        return "Rolling {} = {}".format(self.formula, "".join(map(lambda r: r if isinstance(r, str) else ("+(" + "+".join(map(lambda d: str(d["roll"]), r["rolls"])) + ")"),self.parts)))

    def getInline(self):
        if self.isCrit() and self.isFail():
            classes = "importantroll"
        elif self.isCrit():
            classes = "fullcrit"
        elif self.isFail():
            classes = "fullfail"
        else:
            classes = ""
        return "<span class='fvtt-inline-roll inlinerollresult showtip {}' data-roll-total='{}' data-roll='{}' original-title='{}'>{}</span>" \
                    .format(classes, self.total,
                        json.dumps(self.toJSON()).replace("\'", '&apos;'),
                        self.getTooltip().replace("\'", '&apos;'), self.total)

    def toJSON(self):
        terms = []
        terms_total = 0
        for part in self.parts:
            if not isinstance(part, dict):
                continue
            active_results = [result for result in part["rolls"] if not result.get("discarded", False)]
            part_total = sum(result["roll"] for result in active_results)
            terms_total += part_total
            if part["faces"] == 0:
                terms.append({
                    'class': 'StringTerm',
                    'options': {},
                    'evaluated': True,
                    'term': self.formula,
                })
                continue
            terms.append({
                'class': 'Die',
                'options': part["options"],
                'evaluated': True,
                'number': part["number"],
                'faces': part["faces"],
                'modifiers': [],
                'results': [{
                    'result': result["roll"],
                    'active': not result.get("discarded", False),
                } for result in part["rolls"]],
            })
        remainder = self.total - terms_total
        if remainder:
            if terms:
                terms.append({
                    'class': 'OperatorTerm',
                    'options': {},
                    'evaluated': True,
                    'operator': '+' if remainder > 0 else '-',
                })
                remainder = abs(remainder)
            terms.append({
                'class': 'NumericTerm',
                'options': {},
                'evaluated': True,
                'number': remainder,
            })
        return {
            'class': 'Roll',
            'options': {},
            'dice': [],
            'formula': self.formula,
            'terms': terms,
            'total': self.total,
            'evaluated': True,
        }