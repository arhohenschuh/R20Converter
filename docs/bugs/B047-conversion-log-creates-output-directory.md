# B047: The conversion log creates the output directory, so every conversion fails

- **Status**: **Fixed in 1.7.3 (F048)**
- **Severity**: Critical (total — no conversion of any kind succeeds on 1.7.1 or 1.7.2)
- **Found**: 2026-08-04, reported from the GUI while converting *Storm over Savage Frontier*
- **Introduced**: 1.7.1, by the `conversion-log.txt` feature itself
- **Component**: `src/R20Converter.py` (`_writeLog`, `convert`)

## Symptom

```
Error converting campaign with R20Converter v1.7.2:
  File "src/R20Converter.py", line 365, in convert
    os.makedirs(self.path)
FileExistsError: [WinError 183] Eine Datei kann nicht erstellt werden, wenn sie
bereits vorhanden ist: 'E:/DOWNLOAD/Data/worlds/storm-over-savage-frontier'
```

The destination did **not** exist beforehand. The converter created it itself,
moments earlier, and then tripped over its own directory.

## Cause

`_writeLog` opened its file lazily and created the output directory to do so:

```python
if self._log_fh is None:
    os.makedirs(self.path, exist_ok=True)      # <-- creates the directory
    self._log_fh = open(os.path.join(self.path, self.LOG_FILENAME), "w", ...)
```

`convert()` opens with a log line, one statement before it creates the directory:

```python
def convert(self):
    self.logInfo("*** Converting Campaign '%s' ***" % ...)   # creates self.path
    os.makedirs(self.path)                                   # FileExistsError
```

There is no ordering in which this works, and no configuration that avoids it:
`logInfo` is unconditionally the first statement of `convert()`. **1.7.1 and
1.7.2 cannot convert anything at all.** Both were released without a conversion
having been run against a real campaign export — the unit suite covered the log's
*content* thoroughly and never asserted that a conversion still starts.

## Why the obvious fix is wrong

Relaxing the second call to `os.makedirs(self.path, exist_ok=True)` removes the
crash and introduces a silent data loss.

That bare `makedirs` is not just directory creation — it is the **collision
check**. `src/main.py` guards the destination explicitly before constructing the
converter:

```python
if os.path.exists(args.path):
    if args.overwrite:
        shutil.rmtree(args.path)
    else:
        print("Destination directory must not exist")
        sys.exit(-1)
```

`GUI.startConversion` has **no equivalent** — it goes straight from
`R20Converter(...)` to `convert()`, and the client sends `overwrite: false`. For
every GUI user, the raising `makedirs` is the only thing preventing a conversion
from being written on top of an existing world. Trading a loud, immediate crash
for a quiet overwrite of a campaign is a strictly worse outcome than the bug.

## Fix (F048)

The log no longer creates anything. It buffers lines while the output directory
is absent and flushes them the moment it appears, which is one statement later:

```python
if self._log_fh is None:
    if not os.path.isdir(self.path):
        self._log_buffer.append(msg)
        return
    self._log_fh = open(...)
    for buffered in self._log_buffer:
        self._log_fh.write("%s\n" % buffered)
```

Directory creation — and therefore the collision check — belongs to `convert()`
alone. No log content is lost.

## Regression tests

`tests/test_conversion_log.py`:

- `test_log_never_creates_the_output_directory` — logging with no directory
  present leaves the path non-existent.
- `test_lines_logged_before_the_directory_exists_are_not_lost` — a line logged
  before the directory exists still appears, in order, once it does.

Both were **negative-controlled**: reverted against the 1.7.2 code they fail,
and the second reproduces the reported `FileExistsError: [WinError 183]`
verbatim.

## Lesson

The unit suite grew from 594 to 644 across 1.7.0–1.7.2 and stayed green through
a release that could not perform its one function. Every test exercised a
component; none exercised a conversion. This is the B011 lesson again, in its
most expensive form — see also the pipeline rule that a green gate against
staging is a *build*, not a release. An end-to-end smoke conversion against a
small real export belongs in the release checklist; `--help` returning 0 proves
only that the imports resolved.
