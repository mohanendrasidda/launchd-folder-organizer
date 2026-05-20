#!/usr/bin/env python3
"""Functional regression tests for organize_folders.py.

Each test runs in a clean tmp dir with HOME overridden so the script's
WATCHED_DIRS (~/Documents, ~/Downloads) resolves under the fixture.

Usage:
    python3 tests/test_organize_folders.py
"""
import os
import sys
import shutil
import tempfile
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "organize_folders.py")

results = []


def record(name, ok, details=""):
    results.append((name, ok, details))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")
    if details and not ok:
        for line in details.splitlines():
            print(f"    {line}")


def run_organize(home_dir, dry_run=False):
    env = os.environ.copy()
    env["HOME"] = home_dir
    cmd = [sys.executable, SCRIPT]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def snapshot_files(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            out.append(os.path.relpath(os.path.join(dp, f), root))
    return sorted(out)


def make_fixture(tmp):
    home = os.path.join(tmp, "home")
    dl = os.path.join(home, "Downloads")
    doc = os.path.join(home, "Documents")
    os.makedirs(dl, exist_ok=True)
    os.makedirs(doc, exist_ok=True)
    return home, dl, doc


def touch(path, content="x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_basic_categorization():
    tmp = tempfile.mkdtemp(prefix="t1_")
    try:
        home, dl, _ = make_fixture(tmp)
        for n in ["installer.dmg", "movie.mp4", "image.heic",
                  "IMG_1234.jpg", "resume.pdf", "homework3.tex",
                  "tax_2024.pdf", "archive.zip", "random.dat"]:
            touch(os.path.join(dl, n))
        r = run_organize(home)
        if r.returncode != 0:
            record("basic_categorization", False, f"exit={r.returncode}")
            return
        files = snapshot_files(dl)
        expected = {
            "installer.dmg": "Installers/",
            "movie.mp4": "Media/",
            "image.heic": "Photos/",
            "IMG_1234.jpg": "Photos/",
            "resume.pdf": "Career/",
            "homework3.tex": "Research/",
            "tax_2024.pdf": "Personal/",
            "archive.zip": "Archives/",
            "random.dat": "Misc/",
        }
        misses = []
        for name, exp_prefix in expected.items():
            hit = [f for f in files if f.endswith(name)]
            if not hit or not hit[0].startswith(exp_prefix):
                misses.append(f"{name}: expected {exp_prefix}*, got {hit}")
        record("basic_categorization", not misses, "\n".join(misses))
    finally:
        shutil.rmtree(tmp)


def test_dry_run_no_moves():
    tmp = tempfile.mkdtemp(prefix="t2_")
    try:
        home, dl, _ = make_fixture(tmp)
        for n in ["installer.dmg", "movie.mp4", "random.pdf"]:
            touch(os.path.join(dl, n))
        before = snapshot_files(dl)
        r = run_organize(home, dry_run=True)
        after = snapshot_files(dl)
        if before != after:
            record("dry_run_no_moves", False, f"before={before} after={after}")
            return
        if "DRY-RUN" not in r.stdout:
            record("dry_run_no_moves", False, f"no DRY-RUN in output: {r.stdout}")
            return
        log_dir = os.path.join(home, "Library", "Logs", "organize-folders")
        if os.path.exists(log_dir):
            record("dry_run_no_moves", False, f"log dir leaked: {log_dir}")
            return
        record("dry_run_no_moves", True)
    finally:
        shutil.rmtree(tmp)


def test_project_routing():
    tmp = tempfile.mkdtemp(prefix="t3_")
    try:
        home, dl, _ = make_fixture(tmp)
        repo = os.path.join(dl, "fake_repo")
        os.makedirs(os.path.join(repo, "src"))
        touch(os.path.join(repo, ".git"))
        touch(os.path.join(repo, "src", "main.py"), "# critical content\n")
        venv = os.path.join(dl, "fake_venv")
        os.makedirs(os.path.join(venv, "bin"))
        os.makedirs(os.path.join(venv, "lib", "python3.11", "site-packages", "numpy"))
        touch(os.path.join(venv, "pyvenv.cfg"))
        touch(os.path.join(venv, "lib", "python3.11", "site-packages",
                           "numpy", "__init__.py"), "# numpy content\n")
        r = run_organize(home)
        if r.returncode != 0:
            record("project_routing", False, f"exit={r.returncode}")
            return
        repo_main = os.path.join(dl, "Code-Projects", "fake_repo", "src", "main.py")
        venv_init = os.path.join(dl, "Code-Projects", "fake_venv", "lib",
                                 "python3.11", "site-packages", "numpy", "__init__.py")
        issues = []
        if not os.path.exists(repo_main):
            issues.append(f"repo missing: {repo_main}")
        elif "critical content" not in open(repo_main).read():
            issues.append("repo content corrupted")
        if not os.path.exists(venv_init):
            issues.append(f"venv missing: {venv_init}")
        elif "numpy content" not in open(venv_init).read():
            issues.append("venv content corrupted")
        record("project_routing", not issues, "\n".join(issues))
    finally:
        shutil.rmtree(tmp)


def test_version_clustering():
    """Regression test for the v0.1.1 bug fix."""
    tmp = tempfile.mkdtemp(prefix="t4_")
    try:
        home, dl, _ = make_fixture(tmp)
        for n in ["paper-1.pdf", "paper-2.pdf", "paper-3.pdf", "lonely.pdf"]:
            touch(os.path.join(dl, n))
        r = run_organize(home)
        if r.returncode != 0:
            record("version_clustering", False, f"exit={r.returncode}")
            return
        all_files = snapshot_files(dl)
        bundled = [f for f in all_files if "-versions/" in f and f.endswith(".pdf")]
        lonely_bundled = [f for f in all_files if "lonely" in f and "-versions/" in f]
        if len(bundled) != 3:
            record("version_clustering", False,
                   f"expected 3 in -versions/, got {bundled} | all={all_files}")
            return
        if lonely_bundled:
            record("version_clustering", False, f"lonely bundled: {lonely_bundled}")
            return
        record("version_clustering", True, f"bundle: {bundled}")
    finally:
        shutil.rmtree(tmp)


def test_idempotency():
    tmp = tempfile.mkdtemp(prefix="t5_")
    try:
        home, dl, _ = make_fixture(tmp)
        for n in ["a.dmg", "b.mp4", "c.zip", "d.pdf"]:
            touch(os.path.join(dl, n))
        run_organize(home)
        snap1 = snapshot_files(dl)
        run_organize(home)
        snap2 = snapshot_files(dl)
        record("idempotency", snap1 == snap2,
               f"diff: added={set(snap2)-set(snap1)} removed={set(snap1)-set(snap2)}")
    finally:
        shutil.rmtree(tmp)


def test_moves_tsv_reversible():
    tmp = tempfile.mkdtemp(prefix="t6_")
    try:
        home, dl, _ = make_fixture(tmp)
        touch(os.path.join(dl, "installer.dmg"), "INSTALLER_PAYLOAD")
        touch(os.path.join(dl, "photo.heic"), "PHOTO_PAYLOAD")
        r = run_organize(home)
        if r.returncode != 0:
            record("moves_tsv_reversible", False, f"exit={r.returncode}")
            return
        tsv = os.path.join(home, "Library", "Logs", "organize-folders", "moves.tsv")
        if not os.path.exists(tsv):
            record("moves_tsv_reversible", False, "no moves.tsv")
            return
        rows = [l.rstrip("\n").split("\t") for l in open(tsv) if l.strip()]
        if not all(len(r) == 3 for r in rows):
            record("moves_tsv_reversible", False, f"bad format: {rows}")
            return
        for _ts, src, dst in rows:
            if not os.path.exists(dst):
                record("moves_tsv_reversible", False, f"dst gone: {dst}")
                return
            os.makedirs(os.path.dirname(src), exist_ok=True)
            shutil.move(dst, src)
        i = os.path.join(dl, "installer.dmg")
        p = os.path.join(dl, "photo.heic")
        if not (os.path.exists(i) and open(i).read() == "INSTALLER_PAYLOAD"):
            record("moves_tsv_reversible", False, "installer payload lost")
            return
        if not (os.path.exists(p) and open(p).read() == "PHOTO_PAYLOAD"):
            record("moves_tsv_reversible", False, "photo payload lost")
            return
        record("moves_tsv_reversible", True, f"{len(rows)} moves reversed")
    finally:
        shutil.rmtree(tmp)


def test_dup_collision():
    tmp = tempfile.mkdtemp(prefix="t7_")
    try:
        home, dl, _ = make_fixture(tmp)
        os.makedirs(os.path.join(dl, "Installers"))
        touch(os.path.join(dl, "Installers", "thing.dmg"), "OLD")
        touch(os.path.join(dl, "thing.dmg"), "NEW")
        r = run_organize(home)
        if r.returncode != 0:
            record("dup_collision", False, f"exit={r.returncode}")
            return
        files = os.listdir(os.path.join(dl, "Installers"))
        if "thing.dmg" not in files:
            record("dup_collision", False, f"original gone: {files}")
            return
        dups = [f for f in files if "__dup" in f]
        if not dups:
            record("dup_collision", False, f"no __dupN: {files}")
            return
        old = open(os.path.join(dl, "Installers", "thing.dmg")).read()
        new = open(os.path.join(dl, "Installers", dups[0])).read()
        record("dup_collision", old == "OLD" and new == "NEW",
               f"old={old} new={new}")
    finally:
        shutil.rmtree(tmp)


def test_filename_edge_cases():
    tmp = tempfile.mkdtemp(prefix="t8_")
    try:
        home, dl, _ = make_fixture(tmp)
        touch(os.path.join(dl, "my big installer.dmg"))
        touch(os.path.join(dl, "ファイル.mp4"))
        touch(os.path.join(dl, "मेरी_फोटो.heic"))
        touch(os.path.join(dl, "archive.tar.gz"))
        touch(os.path.join(dl, "screenshot 2024.png"))
        r = run_organize(home)
        if r.returncode != 0:
            record("filename_edge_cases", False, f"exit={r.returncode}")
            return
        files = snapshot_files(dl)
        issues = []
        if not any("Installers/my big installer.dmg" == f for f in files):
            issues.append(f"whitespace dmg: {[f for f in files if 'installer' in f.lower()]}")
        if not any("Media/" in f and "ファイル" in f for f in files):
            issues.append(f"japanese mp4: {[f for f in files if 'mp4' in f]}")
        if not any("Photos/" in f and "मेरी" in f for f in files):
            issues.append(f"hindi heic: {[f for f in files if 'heic' in f]}")
        if not any("Archives/archive.tar.gz" == f for f in files):
            issues.append(f"multi-dot: {[f for f in files if 'tar' in f]}")
        if not any("Photos/" in f and "screenshot" in f.lower() for f in files):
            issues.append(f"screenshot: {[f for f in files if 'screenshot' in f.lower()]}")
        record("filename_edge_cases", not issues, "\n".join(issues))
    finally:
        shutil.rmtree(tmp)


def test_skip_behaviors():
    tmp = tempfile.mkdtemp(prefix="t9_")
    try:
        home, dl, _ = make_fixture(tmp)
        touch(os.path.join(dl, ".hidden.dmg"))
        os.makedirs(os.path.join(dl, "Installers"))
        touch(os.path.join(dl, "Installers", "preexisting.dmg"))
        r = run_organize(home)
        if r.returncode != 0:
            record("skip_behaviors", False, f"exit={r.returncode}")
            return
        if not os.path.exists(os.path.join(dl, ".hidden.dmg")):
            record("skip_behaviors", False, "dotfile moved")
            return
        if not os.path.exists(os.path.join(dl, "Installers", "preexisting.dmg")):
            record("skip_behaviors", False, "preexisting disturbed")
            return
        record("skip_behaviors", True)
    finally:
        shutil.rmtree(tmp)


def test_missing_dirs():
    tmp = tempfile.mkdtemp(prefix="t10_")
    try:
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        r = run_organize(home)
        record("missing_dirs", r.returncode == 0,
               f"exit={r.returncode} stderr={r.stderr}")
    finally:
        shutil.rmtree(tmp)


def test_symlinks():
    tmp = tempfile.mkdtemp(prefix="t11_")
    try:
        home, dl, _ = make_fixture(tmp)
        outside = os.path.join(tmp, "outside.dmg")
        touch(outside, "OUTSIDE_PAYLOAD")
        os.symlink(outside, os.path.join(dl, "linked.dmg"))
        r = run_organize(home)
        if r.returncode != 0:
            record("symlinks", False, f"exit={r.returncode}")
            return
        if not os.path.exists(outside) or open(outside).read() != "OUTSIDE_PAYLOAD":
            record("symlinks", False, "outside file affected")
            return
        record("symlinks", True)
    finally:
        shutil.rmtree(tmp)


TESTS = [
    test_basic_categorization,
    test_dry_run_no_moves,
    test_project_routing,
    test_version_clustering,
    test_idempotency,
    test_moves_tsv_reversible,
    test_dup_collision,
    test_filename_edge_cases,
    test_skip_behaviors,
    test_missing_dirs,
    test_symlinks,
]

for t in TESTS:
    try:
        t()
    except Exception as e:
        import traceback
        record(t.__name__, False, f"exception: {e}\n{traceback.format_exc()}")

print()
n_pass = sum(1 for _, ok, _ in results if ok)
n_fail = sum(1 for _, ok, _ in results if not ok)
print(f"=== {n_pass} passed, {n_fail} failed of {len(results)} ===")
sys.exit(0 if n_fail == 0 else 1)
