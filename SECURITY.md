# Security Policy

## Scope

This is a local-only utility. It:

- Reads files in `~/Documents` and `~/Downloads`.
- Moves files within those directories into category subdirectories.
- Writes logs to `~/Library/Logs/organize-folders/`.
- Runs as a per-user `launchd` agent under your own user account.

It does **not**:

- Make any network calls.
- Use any external dependencies (Python stdlib only).
- Require or use elevated (sudo / root) privileges.
- Transmit any data anywhere.

The attack surface is therefore limited to (a) bugs in the file-move 
logic that could destroy or misplace data, and (b) supply-chain risk 
from the GitHub repository itself.

## Supported versions

Only the latest tagged release receives security fixes. Older versions 
are not maintained.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** to submit 
issues:

https://github.com/mohanendrasidda/launchd-folder-organizer/security/advisories/new

Do not open a public issue for security reports.

I'll acknowledge within 7 days and aim to publish a fix in the 
following release. If the issue requires a coordinated disclosure 
timeline, say so in the report.

## Hardening notes for users

- Review `organize_folders.py` before installing. It's ~300 lines of 
  stdlib Python; reading it end-to-end takes about 10 minutes.
- The `launchd` plist runs the script under your own user account, 
  not as root. Confirm this by reading 
  `~/Library/LaunchAgents/com.user.organize-folders.plist`.
- Logs in `~/Library/Logs/organize-folders/moves.tsv` make every move 
  reversible. If something goes wrong, you can roll back any run.
