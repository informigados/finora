# Finora Build and Distribution Guide

This document describes the official release flow for Finora (Windows executable + Inno Setup installer).

## 1. Prerequisites

Create a clean environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pyinstaller-hooks-contrib
```

Install Inno Setup 6:

- https://jrsoftware.org/isinfo.php

## 2. Release Version

Release version is centralized in the `VERSION` file at project root.

Example:

```text
1.0.0
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

## 4. PyInstaller Build (Executable Only)

Use the official script (clean + deterministic build from `Finora.spec`):

```powershell
.\build_exe.bat
```

Output:

- `dist\Finora\Finora.exe`

Notes:

- The executable icon is set from `static\favicon.ico`.
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

Expected output:

- `dist\Finora\Finora.exe`
- `dist_setup\Finora_Setup_v<version>.exe`

## 6. Direct Inno Setup Compilation (Optional)

If you already generated `dist\Finora`, you can compile manually:

```powershell
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.0.0 finora_installer.iss
```

## 7. Database Migration Requirement

Always migrate schema before publishing a release:

```powershell
flask db upgrade
```

This is critical for fields such as `user.session_timeout_minutes`.

## 8. Release Checklist

1. `python -m pytest tests -q` passes
2. `flask db upgrade` executed successfully
3. `python -m babel.messages.frontend compile -d translations` executed
4. `VERSION` updated to target release
5. `python create_installer.py` generated both EXE and Setup
6. Smoke test login, dashboard, import/export, backup, and profile update

## 9. Recommended GitHub Release Contents

- Source code (tagged)
- `Finora_Setup_v<version>.exe`
- Changelog
- Upgrade notes (especially migration requirements)
