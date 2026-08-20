# R20Converter Repository

## Write lease

Take the repository-scoped lease before modifying source, tests, documentation, commits, tags, or
remote state. Read-only inspection, audits, searches, and comparisons do not require the lease.
The lock is local to this repository and does not block reads or writes in another repository.

```powershell
python G:\Make\GitDev\DnD\tools\agent\werkstatt_lauf.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  nehmen --wer "who you are" --minuten 45

python G:\Make\GitDev\DnD\tools\agent\werkstatt_lauf.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  verlaengern --marke <token> --minuten 45

python G:\Make\GitDev\DnD\tools\agent\werkstatt_lauf.py `
  --lock D:\Automation_Local\Locks\r20converter-repo-write.lock `
  freigeben --marke <token>
```

Exit code `3` means another R20Converter writer owns the lease; do not begin writes. Exit code `4`
while checking or extending means this writer lost the lease; stop writing immediately. The lease
is advisory and machine-local, so every writer must follow this procedure.

## Release validation

1. Add a regression that fails against the preceding release.
2. Run the focused test, then the complete shipping Python 3.8 suite.
3. Update `src/version.py`, `Changelog.md`, `ROADMAP.md`, and the relevant ADR/bug records.
4. Build with the shipping Python 3.8 environment: `python setup.py build`.
5. Verify both frozen entry points report the intended version and frozen `plyvel` can round-trip a
   LevelDB pack.
6. Archive and hash the exact build before advancing to another version.