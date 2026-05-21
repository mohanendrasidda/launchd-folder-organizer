# Contributing

Thanks for considering a contribution. This is a small, focused utility 
— please keep changes equally focused.

## Before you start

- For anything beyond a typo fix, **open an issue first** to discuss 
  the change. Saves both of us time if the idea doesn't fit the 
  project's scope.
- This project deliberately avoids: external dependencies, network 
  calls, AI/LLM integrations, and features that would require running 
  with elevated privileges.

## Development workflow

1. Fork the repo and create a feature branch from `main`.
2. Make your change. Keep the diff minimal — if you find yourself 
   touching unrelated code, split it into a separate PR.
3. Run the full test harness:
```bash
   python3 tests/test_organize_folders.py
```
   All 11 tests must pass. If your change adds new behavior, add a 
   test case for it.
4. Update `README.md` if your change affects user-facing behavior 
   (install steps, configuration, file layouts, log formats).
5. Update `CHANGELOG.md` with an entry under an unreleased section 
   following the existing format.
6. Open a pull request. Describe what changed and why, and confirm 
   the test harness passes locally.

## Style

- Python: stdlib only. No new dependencies without a discussion in 
  an issue first.
- Match the existing code style (PEP 8, no formatter applied — keep 
  changes consistent with surrounding lines).
- Shell scripts: keep `set -euo pipefail` at the top. Run 
  `shellcheck` on any changes.

## What I won't merge

- Code that adds external dependencies (network, pip packages, AI 
  services).
- Code that requires `sudo` or modifies anything outside the user's 
  home directory.
- Changes that break the reversibility guarantee (every move must 
  remain reversible via `moves.tsv`).
- Refactors that don't carry their own justification (style-only PRs 
  without behavior change).

## Reporting bugs

Open an issue with: macOS version, Python version (`python3 
--version`), what you expected, what happened, and relevant lines 
from `~/Library/Logs/organize-folders/organize.log`.

## Security

See [SECURITY.md](SECURITY.md) — please use private vulnerability 
reporting for anything security-related rather than a public issue.
