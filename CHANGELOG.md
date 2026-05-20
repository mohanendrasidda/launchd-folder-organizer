# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.1] — 2026-05-20

### Fixed

- `base_name()` now strips the file extension before applying the
  version-suffix regex. Without this fix, files like `paper-1.pdf` and
  `paper-2.pdf` did not cluster into `paper-versions/` because the
  trailing-digit regex was anchored to the end of the full filename,
  past the extension. The clustering claim in the v0.1.0 README was
  effectively non-functional for any file with an extension.
- Bundle directory naming uses the file stem instead of the full
  filename, so bundles are named `paper-versions/` instead of
  `paper-3.pdf-versions/`.
- Existing-bundle detection (the lookup that lets new siblings join an
  already-created `-versions/` directory) was affected by the same bug
  and is now fixed.

### Added

- `tests/test_organize_folders.py`: an 11-case functional regression
  suite. Runs against tmp directories with HOME overridden. Includes
  a regression test for the v0.1.1 bug. Run with
  `python3 tests/test_organize_folders.py`.

## [0.1.0] — 2026-05-20

Initial public release.
