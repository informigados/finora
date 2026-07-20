# Finora Build and Distribution Guide

This document describes the official release flow for Finora (Windows executable + Inno Setup installer).

## 1. Prerequisites

Create a clean environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Install Inno Setup 6:

- https://jrsoftware.org/isinfo.php

Linux/macOS note:

- `gunicorn` is included only for non-Windows environments and is not used in the official Windows executable/installer flow.
- The packaged Windows distribution uses `waitress`, while `gunicorn` is intended only for direct source deployments on Unix-like systems.

## 2. Release Version

Release version is centralized in the `VERSION` file at project root.

Example:

```text
1.4.1
```

Before generating a release, update this file to the target version.

## 3. One-Command Release (Recommended)

Use the release script:

```powershell
.\release.bat
```

This command will:

1. Read the target version from `VERSION`
2. Ensure virtual environment and dependencies
3. Run test suite (`pytest`)
4. Generate executable and installer (`create_installer.py`)

Expected output:

- `dist\Finora\Finora.exe`
- `dist_setup\Finora_Setup_v<version>.exe`
- `dist_setup\SHA256SUMS.txt`
- `dist_setup\release-metadata.json`
- `dist_setup\manifest.json`

The generated installer is accompanied by a SHA-256 checksum, release metadata, and an update manifest. Public GitHub releases also receive a build-provenance attestation from the release workflow.

## 4. PyInstaller Build (Executable Only)

Use the official script (clean + deterministic build from `Finora.spec`):

```powershell
.\build_exe.bat
```

Output:

- `dist\Finora\Finora.exe`

Notes:

- The executable icon is set from the multi-size `static\favicon.ico`, regenerated from the official source in `icons\finora-icone-fundo-azul.png`.
- Packaged runs automatically use the `desktop` configuration: Waitress on `127.0.0.1`, debug disabled, and writable data under `%LOCALAPPDATA%\Finora` by default.
- Set `FINORA_DATA_DIR` before starting the application only when a custom desktop data location is required.
- The script compiles translations and removes old `build/`, `dist/`, and `dist_setup/` folders first.

## 5. Full Installer Build (Executable + Setup)

Use the release orchestrator:

```powershell
python create_installer.py
```

This command will:

1. Read version from `VERSION`
2. Clean old build artifacts
3. Compile translations
4. Build executable via PyInstaller (`Finora.spec`)
5. Compile `finora_installer.iss` with `MyAppVersion`
6. Generate checksum, provenance metadata, and remote update manifest files

Expected output:

- `dist\Finora\Finora.exe`
- `dist_setup\Finora_Setup_v<version>.exe`

## 6. Direct Inno Setup Compilation (Optional)

If you already generated `dist\Finora`, you can compile manually:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.4.1 finora_installer.iss
```

## 7. Database Migration Requirement

Always migrate schema before publishing a release:

```powershell
flask db upgrade
```

This is critical for fields such as `user.session_timeout_minutes`.
The migration chain is also expected to bootstrap a fresh local SQLite database from zero without manual table creation or stamping.

## 8. Release Checklist

1. `python -m pip install -r requirements-dev.txt`
2. `ruff check .`
3. `bandit -q -r app.py desktop.py config.py database models routes services extensions.py`
4. `pip-audit -r requirements.txt`
5. `python -m pytest tests -q --cov=app --cov=config --cov=database --cov=extensions --cov=models --cov=routes --cov=services --cov-fail-under=90`
6. `flask db upgrade` executed successfully
7. If migrations changed, validate `flask db upgrade` on a fresh local database as well
8. `python -m babel.messages.frontend compile -d translations` executed
9. `VERSION` updated to target release
10. `python create_installer.py` generated both EXE and Setup
11. Smoke test login, dashboard, import/export, backup center, recovery key actions, `/about` update check, and profile observability
12. Confirm production log output is being written to `logs/finora.log` (or the configured log path)
13. If `UPDATE_MANIFEST_URL` is configured, validate version check and pre-update backup flow in a controlled environment
14. Confirm every frontend asset is served locally with external network requests blocked
15. Launch the executable twice and confirm the second process reopens the existing instance instead of starting another server
16. Install over a populated 1.3 profile and confirm database, secret, profile images, and backups migrate to `%LOCALAPPDATA%\Finora`
17. Recalculate the installer SHA-256 and confirm it matches `SHA256SUMS.txt`
18. Install and uninstall in a clean Windows user profile; confirm user data is preserved unless explicitly removed

## 9. Rollback Checklist

If a release must be rolled back, use this sequence:

1. Disable external distribution of the faulty installer/release asset
2. Restore the previous tagged installer/executable
3. If the database schema was migrated forward, verify downgrade feasibility before changing binaries
4. Restore the last known-good backup before any incompatible schema/data migration
5. Validate login, dashboard, import/export, managed backup flow, and recurring maintenance after rollback
6. Record incident date, version, migration state, and remediation notes

## 10. Recommended GitHub Release Contents

- Source code (tagged)
- `Finora_Setup_v<version>.exe`
- Changelog
- Upgrade notes (especially migration requirements)
- Update manifest notes when the release is intended to be consumed by the built-in updater
- `SHA256SUMS.txt`
- `release-metadata.json`
- `manifest.json`

## 11. Automated Windows Release

The `Windows Release` workflow runs when a `v*` tag is pushed. The tag must match `VERSION` exactly (for example, `v1.4.1`). The workflow reruns lint, security auditing, tests, builds the installer, generates a GitHub artifact attestation, and publishes the GitHub Release with SHA-256 verification material.
