# Finora Build and Distribution Guide

This document describes how to package and distribute Finora for production use.

## 1. Build Prerequisites

Install dependencies in a clean virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pyinstaller-hooks-contrib
```

Compile translation binaries before packaging:

```powershell
pybabel compile -d translations
```

## 2. Database Migration Requirement

Always migrate database schema before publishing a release:

```powershell
flask db upgrade
```

This is critical for new columns such as `user.session_timeout_minutes`.

## 3. PyInstaller Build

PyInstaller builds native binaries for the current OS only.
Run a build on each target operating system.

### Windows

```powershell
pyinstaller --noconfirm --onedir --windowed --name "Finora" `
  --add-data "templates;templates" `
  --add-data "static;static" `
  --add-data "translations;translations" `
  --hidden-import "babel.numbers" `
  --hidden-import "waitress" `
  app.py
```

### Linux

```bash
pyinstaller --noconfirm --onedir --windowed --name "Finora" \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --add-data "translations:translations" \
  --hidden-import "babel.numbers" \
  --hidden-import "waitress" \
  app.py
```

### macOS

```bash
pyinstaller --noconfirm --onedir --windowed --name "Finora" \
  --add-data "templates:templates" \
  --add-data "static:static" \
  --add-data "translations:translations" \
  --target-arch universal2 \
  app.py
```

## 4. Installer and Signing

### Windows Installer (Inno Setup)

Use `finora_installer.iss` after generating `dist/Finora`.

### Code Signing

Sign release binaries to reduce SmartScreen/Gatekeeper warnings.

#### Windows

```powershell
"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe" sign /f "certificate.pfx" /p "password" /tr http://timestamp.digicert.com /td sha256 /fd sha256 "dist\Finora\Finora.exe"
```

#### macOS

```bash
codesign --deep --force --verbose --sign "Developer ID Application: Name (TEAMID)" dist/Finora.app
```

## 5. Container Build

Build and run with Docker:

```powershell
docker compose build
docker compose up -d
```

## 6. Release Checklist

1. `python -m pytest tests -q` passes
2. `flask db upgrade` executed successfully
3. `pybabel compile -d translations` executed
4. Binary starts and login works with existing database
5. Import/export and backup smoke-tested
6. Versioned artifacts prepared and signed (if applicable)

## 7. Recommended GitHub Release Contents

- Source code (tagged)
- Platform binaries (`Windows/Linux/macOS`)
- Changelog with migration notes
- Upgrade instructions (especially database migrations)
