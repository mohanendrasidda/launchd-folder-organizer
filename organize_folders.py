#!/usr/bin/env python3
"""Daily folder organizer for macOS.

Categorizes new top-level items in watched directories (default: ~/Documents
and ~/Downloads) into subfolders by type. Designed to run unattended via
launchd. Moves are logged to a TSV so they can be reversed.

Usage:
    organize_folders.py            # run, applying moves
    organize_folders.py --dry-run  # print planned moves, change nothing
"""
import os
import re
import sys
import shutil
import argparse
import collections
import datetime
import traceback

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

HOME = os.path.expanduser('~')

# Directories whose top-level entries should be categorized.
WATCHED_DIRS = [
    os.path.join(HOME, 'Documents'),
    os.path.join(HOME, 'Downloads'),
]

# Absolute paths (or basenames relative to a watched dir) to leave alone.
# Useful when a directory under ~/Documents holds files whose paths are
# referenced by scripts, IDE projects, or research pipelines.
#
# Examples (uncomment and edit to taste):
#   SKIP_DIRS = ['my-active-experiment', 'data-pipeline-runs']
SKIP_DIRS = []

# Top-level marker files/dirs whose presence flags a directory as a project
# root. Directories with any of these markers are routed to Code-Projects/
# as a unit (their internal layout is preserved). This is what protects
# active git repos, virtualenvs, and package roots from being walked into.
PROJECT_MARKERS = [
    '.git',
    'package.json',
    'pyproject.toml',
    'requirements.txt',
    'Pipfile',
    'Cargo.toml',
    'go.mod',
    '.venv',
    'venv',
    'node_modules',
]

# Categories. The script creates a subfolder per category under each watched
# dir as needed. Entries already named like a category are skipped on
# subsequent runs (idempotent).
CATEGORIES = [
    'Research',
    'Coursework',
    'Career',
    'Code-Projects',
    'Personal',
    'Photos',
    'Media',
    'Installers',
    'Archives',
    'Misc',
]

# Where logs and the moves TSV go. The directory is created on first run.
LOG_DIR = os.path.join(HOME, 'Library', 'Logs', 'organize-folders')

# Keyword lists used to route by filename. RESEARCH_KEYWORDS is checked
# with a substring match; the others use regex via re.search.
#
# Optional: add filename substrings that should route to a Research/ folder.
# Left empty by default — populate based on your own work. Files with
# LaTeX extensions and the `main*` prefix still route to Research/ via the
# dedicated rules below.
RESEARCH_KEYWORDS = []
COURSEWORK_PATTERNS = [
    'homework', r'^hw[\s\-_]*\d', 'syllabus', 'assignment', 'lecture',
    'exam', 'quiz', 'midterm', r'final[\s\-_]', r'lab[\s\-_]',
    r'cheat[\s\-_]?sheet', r'\bcs(?:ce)?\s*\d{3,4}\b',
]
CAREER_PATTERNS = [
    'resume', r'\bcv\b', 'internship', r'(?<![a-z])job(?![a-z])',
    'application', 'interview', 'offer', r'cover[\s\-_]?letter',
    'recommendation', 'transcript',
]
PERSONAL_PATTERNS = [
    'tax', 'lease', 'rental', 'medical', 'health', 'passport', 'license',
    'insurance', 'invoice', 'receipt',
]

# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

CATEGORY_SET = set(CATEGORIES)
LOG_FILE = os.path.join(LOG_DIR, 'organize.log')
MOVES_FILE = os.path.join(LOG_DIR, 'moves.tsv')


def log(msg):
    ts = datetime.datetime.now().isoformat(timespec='seconds')
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{ts}] {msg}\n")


def is_skipped(name, root):
    if name in SKIP_DIRS:
        return True
    if os.path.join(root, name) in SKIP_DIRS:
        return True
    return False


def detect_markers(path):
    if not os.path.isdir(path):
        return ''
    found = []
    for m in PROJECT_MARKERS:
        if os.path.exists(os.path.join(path, m)):
            found.append(m)
    # A directory containing both `bin/` and `lib/pythonX.Y/` is almost
    # certainly a virtualenv even without an explicit marker file.
    lib = os.path.join(path, 'lib')
    bin_ = os.path.join(path, 'bin')
    if os.path.isdir(lib) and os.path.isdir(bin_):
        try:
            for sub in os.listdir(lib):
                if sub.startswith('python'):
                    found.append('venv-heuristic')
                    break
        except OSError:
            pass
    return ','.join(found)


def categorize(name, kind, markers, parent):
    n = name.lower()
    ext = os.path.splitext(n)[1]

    if is_skipped(name, parent):
        return None
    if markers:
        return 'Code-Projects'

    if ext in ('.dmg', '.pkg', '.iso', '.exe', '.msi', '.deb', '.rpm', '.app'):
        return 'Installers'
    if ext in ('.mkv', '.mp4', '.mov', '.avi', '.webm', '.m4v', '.flv', '.wmv'):
        return 'Media'
    if ext in ('.heic', '.heif'):
        return 'Photos'
    if re.match(r'^(img_|dsc_|pxl_|whatsapp\s+image|screenshot|screen\s+shot|photo)', n):
        return 'Photos'
    if re.match(r'^\d{8}_\d{6}', n):
        return 'Photos'
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp') and re.match(r'^[a-z0-9_\-]{16,}\.', n):
        return 'Photos'

    if any(kw in n for kw in RESEARCH_KEYWORDS):
        return 'Research'
    if ext in ('.tex', '.bib', '.cls', '.sty', '.bbl', '.nbib'):
        return 'Research'
    if re.match(r'^main[\s\-_]', n) or n.startswith('main.') or re.match(r'^main\d', n):
        return 'Research'

    if any(re.search(p, n) for p in COURSEWORK_PATTERNS):
        return 'Coursework'

    if any(re.search(p, n) for p in CAREER_PATTERNS):
        return 'Career'

    if any(re.search(p, n) for p in PERSONAL_PATTERNS):
        return 'Personal'
    if ext in ('.ics', '.eml', '.vcf'):
        return 'Personal'

    if ext in ('.zip', '.tar', '.gz', '.tgz', '.7z', '.rar', '.bz2', '.xz'):
        return 'Archives'

    return 'Misc'


def base_name(name):
    stem, _ = os.path.splitext(name)
    s = re.sub(r'\s*\(\d+\)\s*$', '', stem)
    s = re.sub(r'[\s\-_]+\d+(?:[\s\-_]+\d+)*$', '', s)
    return s.lower()


def organize_root(root, dry_run=False):
    moved = 0
    skipped = 0
    if not os.path.isdir(root):
        return 0, 0

    items = []
    for name in os.listdir(root):
        if name.startswith('.'):
            continue
        if name in CATEGORY_SET:
            continue
        if is_skipped(name, root):
            continue
        path = os.path.join(root, name)
        kind = 'D' if os.path.isdir(path) else 'F'
        markers = detect_markers(path) if kind == 'D' else ''
        items.append({'name': name, 'kind': kind, 'markers': markers, 'path': path})

    if not items:
        return 0, 0

    plan = []
    for it in items:
        cat = categorize(it['name'], it['kind'], it['markers'], root)
        plan.append({**it, 'category': cat})

    sibling_groups = collections.defaultdict(list)
    for p in plan:
        if p['category'] is None:
            continue
        key = (p['category'], base_name(p['name']))
        sibling_groups[key].append(p['name'])

    bundles = {}
    for (cat, _base), names in sibling_groups.items():
        existing = []
        cat_dir = os.path.join(root, cat)
        longest_stem, _ = os.path.splitext(max(names, key=len))
        prefix = re.sub(r'[\s\-_]+\d+(?:[\s\-_]+\d+)*$', '', longest_stem)
        prefix = re.sub(r'\s*\(\d+\)\s*$', '', prefix)
        if os.path.isdir(cat_dir):
            for sub in os.listdir(cat_dir):
                if sub.endswith('-versions') and sub.startswith(prefix):
                    existing.append(sub)
        if len(names) >= 2 or existing:
            bundle = f"{prefix}-versions"
            for n in names:
                bundles[n] = bundle

    movelog = None if dry_run else open(MOVES_FILE, 'a')
    try:
        for p in plan:
            if p['category'] is None:
                skipped += 1
                continue
            src = p['path']
            if not os.path.exists(src):
                skipped += 1
                continue
            cat_dir = os.path.join(root, p['category'])
            bundle = bundles.get(p['name'])
            dst_dir = os.path.join(cat_dir, bundle) if bundle else cat_dir
            dst = os.path.join(dst_dir, p['name'])
            if os.path.exists(dst):
                base, ext = os.path.splitext(dst)
                i = 1
                while os.path.exists(f"{base}__dup{i}{ext}"):
                    i += 1
                dst = f"{base}__dup{i}{ext}"

            if dry_run:
                print(f"DRY-RUN: {src} -> {dst}")
                moved += 1
                continue

            try:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.move(src, dst)
                moved += 1
                ts = datetime.datetime.now().isoformat(timespec='seconds')
                movelog.write(f"{ts}\t{src}\t{dst}\n")
            except Exception as e:
                log(f"ERROR moving {src} -> {dst}: {e}")
                skipped += 1
    finally:
        if movelog is not None:
            movelog.close()

    return moved, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dry-run', action='store_true',
                        help='Print planned moves without changing anything.')
    args = parser.parse_args()

    if not args.dry_run:
        os.makedirs(LOG_DIR, exist_ok=True)
        log(f"=== run start (pid {os.getpid()}) ===")

    total_moved = 0
    total_skipped = 0
    for root in WATCHED_DIRS:
        try:
            m, s = organize_root(root, dry_run=args.dry_run)
            if args.dry_run:
                print(f"# {root}: planned moves={m} skipped={s}")
            else:
                log(f"{root}: moved={m} skipped={s}")
            total_moved += m
            total_skipped += s
        except Exception as e:
            err = f"FATAL in {root}: {e}\n{traceback.format_exc()}"
            if args.dry_run:
                print(err, file=sys.stderr)
            else:
                log(err)

    if args.dry_run:
        print(f"# total planned moves={total_moved} skipped={total_skipped}")
    else:
        log(f"=== run end: total moved={total_moved} skipped={total_skipped} ===")
    return 0


if __name__ == '__main__':
    sys.exit(main())
