# B113: Redirected console output crashes on non-cp1252 characters

- Severity: High
- Status: Fixed in v1.16.2
- Observed release: R20Converter 1.16.1 Windows build (`R20Converter-cli.exe`)
- Reported: 24 October 2026, Dragoncoast Danger played-world reconversion (`dcd/v130`)

## Reproduction

Run `R20Converter-cli.exe` with stdout/stderr redirected to a file or pipe (for example
`R20Converter-cli.exe ... *> conversion.log` in PowerShell, or `| Tee-Object` as the module
driver does) on a campaign whose warning text contains a character outside Windows-1252.
Dragoncoast Danger (R20Exporter 1.5.3, SHA-256 `0397FED9...4639D3`) contains U+2060 WORD
JOINER in a Macro link target. The run aborts while converting Macros:

```text
File "src\entities\base.py", line 497, in _foundJournal
  self.logWarning("Roll20 %s link '%s' targets a document absent from the export" ...)
File "src\utils.py", line 101, in logWarning
  print(msg)
UnicodeEncodeError: 'charmap' codec can't encode character '\u2060' in position 22
```

`PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` have no effect on the frozen executable. Running
the same command attached to an interactive console succeeds, because the console uses the
wide-character API.

## Cause

`utils.Logger` writes with `print()`. When stdout is not a console, the frozen Python 3.8
runtime encodes with the ANSI code page (cp1252) in strict mode, so a single unencodable
character in any log line aborts the whole conversion.

## Expected Behavior

Logging never aborts a conversion. Reconfigure stdout/stderr to UTF-8 (for example
`sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')` at start-up) or make the
logger encode safely, and keep the complete log text.

## Regression Requirements

- Running the CLI with redirected output on a fixture whose warning contains U+2060 and
  U+2028 completes and writes both characters (or explicit escapes) to the log.
- A run with only ASCII warnings is unchanged.

## Generic Resolution

Startup configures text stdout and stderr as UTF-8 with `backslashreplace` before loading the
application. GUI fallback streams use `StringIO`, not binary buffers. The existing UTF-8
conversion log remains intact. Strict CP1252 subprocess controls reproduce the old failure;
Unicode and ASCII tests cover all three logger levels in
[test_conversion_log.py](../../tests/test_conversion_log.py).
