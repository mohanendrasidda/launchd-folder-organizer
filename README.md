# launchd-folder-organizer

A small macOS daemon that categorizes new top-level items in `~/Documents` and `~/Downloads` into subfolders by type, on a daily schedule.

## Why

Watched directories like `~/Downloads` accumulate noise: installers, screenshots, papers, zips, one-off PDFs. Manual cleanup is tedious; aggressive cleanup tools tend to walk into active git repos and virtualenvs and break things. This script is the smaller idea — a single Python file, scheduled by `launchd`, that moves *top-level* entries into a fixed set of categories, preserves project directories as-is, and writes a reversible TSV of every move it makes.

## Features

- **Ten fixed categories** — `Research`, `Coursework`, `Career`, `Code-Projects`, `Personal`, `Photos`, `Media`, `Installers`, `Archives`, `Misc`. Routing is by extension + filename keyword.
- **Project-aware categorization** — directories containing `.git`, `package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, `Cargo.toml`, `go.mod`, `.venv`, `venv`, or `node_modules` are moved as a single unit into `Code-Projects/`. The script will not recurse into them or reorganize their internals.
- **Virtualenv heuristic** — directories with both `bin/` and `lib/pythonX.Y/` are treated as projects even without a marker file.
- **Version-sibling clustering** — when two or more entries share a category and normalize to the same base name (e.g. `paper-1.pdf`, `paper-2.pdf`, `paper (3).pdf`), they are bundled into `<category>/<base>-versions/`. The file extension is stripped before normalization, so `paper-1.pdf` clusters as `paper`. Files with different extensions still cluster as long as they end up in the same category. Only trailing `-N`, `_N`, ` N`, or `(N)` suffixes are recognized as version markers — `paper-v1.pdf` is not. Pre-existing `-versions/` folders also attract new siblings.
- **Reversible** — every move is appended to `~/Library/Logs/organize-folders/moves.tsv` as `timestamp \t src \t dst`. A one-liner restores any subset.
- **Idempotent** — entries whose names already match a category are skipped on subsequent runs, so re-running is safe.
- **Catch-up on wake** — uses `StartCalendarInterval`, so a job missed while the Mac was asleep runs on next wake.
- **`--dry-run` mode** — prints the plan to stdout, changes nothing.

## Requirements

- macOS 12 (Monterey) or later. Tested on 14 (Sonoma) and 15 (Sequoia).
- Python 3.9+ (the system `/usr/bin/python3` works).
- No third-party packages.

## Install

```bash
git clone https://github.com/mohanendrasidda/launchd-folder-organizer.git
cd launchd-folder-organizer
./install.sh
```

`install.sh` copies the script into `~/bin/`, materializes the plist with your `$HOME` substituted in, and loads the agent with `launchctl bootstrap`.

### Recommended first run: dry-run

Before letting the scheduled agent move anything, run the script once in `--dry-run` mode against your real directories. Nothing is moved and `moves.tsv` is not touched — you just see the plan on stdout:

```bash
~/bin/organize-folders.py --dry-run
```

If the plan looks wrong, edit the keyword lists in `~/bin/organize-folders.py` (see [Configuration](#configuration)) and re-run the dry-run until it does. Then either wait for the scheduled 3 AM tick or `launchctl kickstart` an immediate run (below).

### Granting Full Disk Access (required)

Under macOS sandboxing, a `launchd` agent cannot read `~/Documents` or `~/Downloads` unless you grant it Full Disk Access. macOS will only grant FDA to a `.app` bundle, not to a bare script, so the standard trick is to wrap the script in a one-line AppleScript applet:

```bash
osacompile -e 'do shell script "$HOME/bin/organize-folders.py"' \
    -o ~/Applications/OrganizeFolders.app
```

(Substitute `$HOME` literally if your shell does not expand it inside `osacompile`.)

Then:

1. Open **System Settings → Privacy & Security → Full Disk Access**.
2. Click **+** and add `~/Applications/OrganizeFolders.app`.
3. Toggle it on.

The plist's `ProgramArguments` points at the applet, so the FDA grant applied to the `.app` flows through to the shell script it spawns. Without this step the first run logs a `PermissionError` and exits.

To trigger an immediate run after install:

```bash
launchctl kickstart -k gui/$(id -u)/com.user.organize-folders
```

## Configuration

All editable settings live in a `CONFIG` section at the top of `organize_folders.py`:

| Setting | Default | What it does |
|---|---|---|
| `WATCHED_DIRS` | `[~/Documents, ~/Downloads]` | Directories whose top-level entries get categorized. |
| `SKIP_DIRS` | `[]` | Basenames (or absolute paths) of entries to leave alone. Use for in-place data folders whose paths are referenced by other scripts. |
| `PROJECT_MARKERS` | `.git`, `package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, `Cargo.toml`, `go.mod`, `.venv`, `venv`, `node_modules` | Files/dirs that, if present at a directory's top level, mark it as a project root. |
| `CATEGORIES` | the ten listed above | Subfolder names. Entries already named like a category are skipped on rescan. |
| `LOG_DIR` | `~/Library/Logs/organize-folders` | Where `organize.log` and `moves.tsv` are written. |
| `RESEARCH_KEYWORDS`, `COURSEWORK_PATTERNS`, `CAREER_PATTERNS`, `PERSONAL_PATTERNS` | generic defaults | Keyword routing. The first list uses substring match; the others use `re.search`. |

Edit, save, and run `--dry-run` to preview the effect before the next scheduled tick.

## Logs

Two files under `~/Library/Logs/organize-folders/`:

- `organize.log` — one line per run boundary, one line per watched dir per run with `moved=N skipped=N`, and full tracebacks on fatal errors.
- `moves.tsv` — append-only, tab-separated, three columns: `ISO_timestamp`, `src`, `dst`. This is the rollback source of truth.

The plist also defines `stdout.log` and `stderr.log` in the same dir; the script writes its own logs, so these usually stay empty unless the wrapper crashes.

## Undoing moves

To reverse every move recorded on or after a given date:

```bash
awk -F'\t' -v cutoff="2026-05-19" '$1 >= cutoff { print $3 "\t" $2 }' \
    ~/Library/Logs/organize-folders/moves.tsv |
while IFS=$'\t' read -r src dst; do
    mkdir -p "$(dirname "$dst")" && mv "$src" "$dst"
done
```

(The columns are swapped in the `awk` step: what was a destination becomes the source, and vice versa.)

To reverse only the last N moves, use `tail -n N` in place of the cutoff filter.

After a successful rollback, prune the reversed rows from `moves.tsv` manually so a second rollback does not try to move files that are no longer there.

## A note on the project-marker list

This script exists because of a near-miss. An earlier one-shot cleanup pass — not this script — descended into a directory under `~/Documents` that turned out to be a Python virtualenv's `site-packages`. About 2,232 files were queued to move before the run was aborted. Nothing was actually lost, but it was close enough that the next attempt was built around a single rule: never reorganize files *inside* directories that look like projects. That rule is the project-marker check.

Concretely, the `PROJECT_MARKERS` list (`.git`, `package.json`, `pyproject.toml`, `requirements.txt`, `Pipfile`, `Cargo.toml`, `go.mod`, `.venv`, `venv`, `node_modules`) is checked at the top level of each directory the script considers. If any marker is present, the whole directory is moved as a unit into `Code-Projects/` — its internals are never touched. This protects absolute paths in virtualenv shebangs (`#!/path/to/.venv/bin/python`), IDE workspace files, and anything else that pinned a location.

Remove markers from the list deliberately. The default set is conservative on purpose. If you have data folders whose absolute paths matter to other scripts and that do *not* carry a marker file, list them in `SKIP_DIRS` instead.

## Limitations

- **Heuristic, not understanding.** Categorization is based on file extension and filename text, not content. A misnamed file ends up in `Misc/`; a generically named one may land in an unexpected category. Use `--dry-run` after editing keyword lists.
- **Top-level only.** The script reads the immediate children of each watched directory. It does not descend into subdirectories to reorganize their contents.
- **No conflict resolution beyond suffixing.** If `Downloads/Misc/foo.pdf` already exists when a second `foo.pdf` is moved in, the new one is renamed `foo__dup1.pdf`. Older `__dup` files are not deduplicated.
- **No content-aware photo detection.** "Photo" is determined by filename pattern (`IMG_`, `DSC_`, `PXL_`, `Screenshot`, etc.), by HEIC/HEIF extension, or by raster extensions with a long hashed-looking basename. A photo named `vacation.jpg` will not be detected and lands in `Misc/`.
- **macOS only.** The script itself is portable Python, but the install path depends on `launchd` and macOS Full Disk Access semantics.

## License

MIT — see `LICENSE`.
