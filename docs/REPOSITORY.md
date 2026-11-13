# R20Converter Repository

## Write lease

Take the repository-scoped lease before modifying source, tests, documentation, commits, tags, or
remote state. Read-only inspection, audits, searches, and comparisons do not require the lease.
The lock is local to this repository and does not block reads or writes in another repository.

```powershell
python G:\Make\GitDev\DnD\tools\agent\workshop_run.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  take --who "who you are" --minutes 45

python G:\Make\GitDev\DnD\tools\agent\workshop_run.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  extend --mark <mark> --minutes 45

python G:\Make\GitDev\DnD\tools\agent\workshop_run.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  release --mark <mark>
```

`take` prints the mark on its last line. `show` reports the current holder, and `owns --mark <mark>`
checks the lease silently before a write. The tool was formerly `werkstatt_lauf.py` with German verbs
(`nehmen`, `verlaengern`, `freigeben`).

Exit code `3` means another R20Converter writer owns the lease; do not begin writes. Exit code `4`
while checking or extending means this writer lost the lease; stop writing immediately. The lease
is advisory and machine-local, so every writer must follow this procedure.

## Release validation

1. Add a regression that fails against the preceding release.
2. Run the focused test, then the complete shipping Python 3.8 suite.
3. Update `src/version.py`, `Changelog.md`, `ROADMAP.md`, and the relevant ADR/bug records.
4. Build with the shipping Python 3.8 environment
   (`D:\Automation_Local\Infrastructure\Toolchains\r20converter\python38`): `python setup.py build`.
   cx_Freeze writes `build\exe.win-amd64-3.8`; rename it to `build\R20Converter-<version>-win-amd64`.
5. Verify both frozen entry points report the intended version and frozen `plyvel` can round-trip a
   LevelDB pack.
6. Archive and hash the exact build before advancing to another version. Releases are archived
   under `D:\Automation_Local\Infrastructure\Toolchains\r20converter\<version>` with their receipts.
7. Tag with an annotated `v<version>` tag that names the archive and its SHA-256. Publish the ZIP
   and `SHA256SUMS.txt` as a GitHub release, then download both again and verify the hash.