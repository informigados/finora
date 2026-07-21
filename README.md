# 💼 Finora

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.x-black)
![Database](https://img.shields.io/badge/database-sqlite%20%7C%20mysql-0f766e)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/informigados/finora/actions/workflows/ci.yml/badge.svg)](https://github.com/informigados/finora/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/informigados/finora)

Finora is a local-first personal finance application built with Flask.  
It provides expense/income tracking, recurring entries, budgets, goals, imports/exports, managed backups, profile observability, guided updates, and multilingual UI.

Current stable version: `1.4.5`

## 🧱 Tech Stack

- Python 3.12+ (tested with Python 3.14)
- Flask, Flask-Login, Flask-Babel, Flask-SQLAlchemy, Flask-Migrate
- SQLite (default), MySQL support via SQLAlchemy URL
- Jinja2 templates + Bootstrap + custom CSS/JS

## 🚀 Core Features

- Welcome landing page before authentication
- Secure authentication flow (register/login/recovery/profile)
- Session timeout policy per user with warning and renewal
- Monthly dashboard with metrics and chart
- Recurring transaction generation
- Budget planning by category (monthly/yearly)
- Financial goals tracking
- Hierarchical financial catalog: type, category, subcategory
- Payment/receiving method tracking in entries, imports, exports, and reports
- Import (CSV/XLSX) with validation and row-level error handling
- Export (PDF/CSV/TXT)
- Managed backup center with manual generation, retention, and automatic scheduling
- Recovery key display, resend, regeneration, and e-mail delivery
- Profile hub with sessions, activity history, system status, and support shortcuts
- Guided update system on `/about` with version check, pre-update backup, and migration-safe apply flow
- Native desktop window with minimize, maximize, close, taskbar presence, and bundled UI resources
- Single-instance desktop launcher that focuses the active Finora window
- Encrypted local SMTP settings under `Meu Perfil > E-mail`, with an integrated delivery test
- Internationalization: Portuguese (default), English, Spanish

## 📁 Project Structure

```text
app.py
config.py
database/
models/
routes/
services/
templates/
static/
translations/
migrations/
tests/
```

## 🪟 Windows Desktop Installation

The official Windows installer is published on the [GitHub Releases page](https://github.com/informigados/finora/releases). Download it only from the official INformigados repository and verify its SHA-256 value against `SHA256SUMS.txt` from the same release.

## ⚙️ Local Setup

1. Create virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment (`.env`):

```ini
SECRET_KEY=change_me
FLASK_ENV=development
# Optional:
# DATABASE_URL=sqlite:///database/finora.db
```

3. Apply database migrations:

```powershell
flask db upgrade
```

4. Run the app:

```powershell
python app.py
```

Or use the helper script:

```powershell
.\run_app.bat
```

Optional:

- `FINORA_AUTO_OPEN_BROWSER=0` disables automatic browser opening on startup.

Optional update and mail settings:

```ini
# App metadata
APP_VERSION=1.4.5
APP_BASE_URL=http://127.0.0.1:5000

# Automatic update
UPDATE_CHANNEL=stable
UPDATE_MANIFEST_URL=
UPDATE_DOWNLOAD_DIR=updates
UPDATE_TARGET_ROOT=.
UPDATE_CHECK_TIMEOUT_SECONDS=20
UPDATE_DOWNLOAD_TIMEOUT_SECONDS=60
UPDATE_NETWORK_RETRY_ATTEMPTS=3
UPDATE_NETWORK_RETRY_BACKOFF_SECONDS=2
UPDATE_ALLOW_LOCAL_ASSETS=0

# Backup automation
ENABLE_BACKUP_SCHEDULER=1
BACKUP_STORAGE_DIR=backups
BACKUP_DEFAULT_RETENTION_COUNT=20

# Mail delivery
MAIL_SERVER=
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_USE_TLS=1
MAIL_USE_SSL=0
MAIL_DEFAULT_SENDER=
MAIL_FROM_NAME=Finora
MAIL_TIMEOUT_SECONDS=10
```

## 👤 Optional Default Test User

Finora supports an optional default user seed for local environments, including local desktop/package runs.

> The official Windows installer does **not** create an `admin/admin123` account. This is intentional: a universal production credential would expose every installation. On first use, select **Create account** and register the local owner. The seed below is restricted to explicitly configured development/test environments.

- Disabled by default (`ENABLE_DEFAULT_USER_SEED=False`)
- Intended for local use only, and only runs when `ENABLE_DEFAULT_USER_SEED=1`
- Requires `DEFAULT_USER_PASSWORD` to be set (otherwise seed is skipped)

Default values used by the seed:

- `DEFAULT_USER_USERNAME=admin`
- `DEFAULT_USER_EMAIL=admin@finora.local`
- `DEFAULT_USER_NAME=Administrador de Teste`

Example `.env` setup:

```ini
ENABLE_DEFAULT_USER_SEED=1
DEFAULT_USER_NAME=Administrador de Teste
DEFAULT_USER_USERNAME=admin
DEFAULT_USER_EMAIL=admin@finora.local
DEFAULT_USER_PASSWORD=admin123
```

## 🔄 Updates and Recovery

- The `/about` page shows the installed version, latest known version, channel, and update status.
- Source runs ship with a local read-only manifest in `updates/manifest.json` for safe development checks.
- Desktop runs use the update manifest attached to the latest GitHub Release by default.
- Desktop updates require an HTTPS installer URL and a matching SHA-256 checksum before they can be staged.
- After validation, Finora creates a data backup, exits safely, launches the installer, and lets the next startup run bundled database migrations.
- The first 1.4 desktop startup automatically migrates pre-1.4 packaged databases, profile images, backups, and the persisted local secret into `%LOCALAPPDATA%\Finora`.
- Source deployments retain the protected ZIP update flow and automatic `flask db upgrade` behavior.
- Local packages referenced by a local manifest stay blocked by default. Only enable `UPDATE_ALLOW_LOCAL_ASSETS=1` for trusted offline update workflows.
- Recovery keys can be copied from the profile, re-emailed, or regenerated.
- In the desktop app, configure SMTP under `Meu Perfil > E-mail`; the password is encrypted and stored only in the user's local application-data directory.
- When SMTP is unavailable, Finora explicitly reports that delivery did not occur and keeps offline recovery available instead of claiming a successful send.

### Updating from 1.4.0 or 1.4.1

Finora 1.4.0 and 1.4.1 may fail while creating their pre-update backup if the embedded WebView2 runtime keeps `webview/EBWebView/lockfile` open. If the `/about` page reports `Permission denied` for that file, download and run the current installer manually from the official GitHub Release once. The installer preserves the data stored under `%LOCALAPPDATA%\Finora`. From version 1.4.2 onward, transient WebView2 files and runtime locks are excluded from pre-update backups, so future in-app updates can proceed normally.

## 👤 Profile Hub and Backups

- `Meu Perfil` centralizes account settings, password changes, recovery key management, backups, sessions, activities, and system status.
- `Meus Backups` supports:
  - manual backup generation
  - automatic daily/weekly/monthly schedules
  - retention policy
  - backup download and deletion
- The profile status area shows:
  - login sessions
  - recent activities
  - system events
  - update status
  - backup and scheduler health

## 🗄️ Database Notes

- Default database: `database/finora.db`
- Production recommendation: managed MySQL or PostgreSQL
- Set database URL through `DATABASE_URL`

Example MySQL URL:

```ini
DATABASE_URL=mysql+mysqldb://user:password@host:3306/finora
```

## 🌐 Online deployment with Docker and MySQL

The repository includes a production profile with MySQL 8.4, automatic Alembic migrations, persistent volumes, container health checks, and a non-root application user.

```bash
cp .env.example .env
# Replace every placeholder and URL-encode special characters in the DATABASE_URL password.
docker compose up -d --build
docker compose ps
```

Required production values:

- `SECRET_KEY`: unique random value with at least 48 characters
- `APP_BASE_URL`: final HTTPS address used in password-reset links
- `DATABASE_URL`: MySQL connection using `mysql+mysqldb` (the driver already included in the project)
- `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`: unique database passwords

Keep `TRUST_PROXY_HEADERS=0` when Finora is exposed directly. Enable it only behind a reverse proxy you control. SMTP remains optional, but password recovery by e-mail is available only when the `MAIL_*` values are configured.

## 🪵 Production Logs

- Production enables rotating file logs by default.
- Default path: `logs/finora.log`
- Rotation defaults: `1 MB` per file with `5` backups
- Request correlation is included through `request_id`

Optional environment variables:

```ini
LOG_TO_FILE=1
LOG_DIRECTORY=logs
LOG_FILE_NAME=finora.log
LOG_MAX_BYTES=1048576
LOG_BACKUP_COUNT=5
SQLALCHEMY_LOG_LEVEL=WARNING
```

By default, SQL query logs stay at `WARNING` to avoid flooding the production terminal.

## 🌍 Internationalization Workflow

Update translation catalog:

```powershell
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d translations
```

Compile translations:

```powershell
pybabel compile -d translations
```

## 🧪 Testing

Run full test suite:

```powershell
python -m pytest tests -q
```

Or:

```powershell
.\run_tests.bat
```

## 🔐 Security and Reliability Notes

- CSRF protection enabled for form and JSON flows
- Runtime compatibility patch included for legacy SQLite schema fields
- Import limits configured (`MAX_CONTENT_LENGTH`, row limit)
- Cookie hardening and secure production settings in `config.py`

## 📝 Changelog

### 2026-03-02 (1.0.0)

- Initial release.

### 2026-03-10 (1.1.0)

- Added robust password reset token flow (1-hour expiry) with dedicated UI and clear local-mode messaging.
- Fixed goals and budgets progress bars rendering and improved accessibility (`role="progressbar"` + ARIA values).
- Implemented responsive mobile navbar with collapse/toggler for small screens.
- Added dashboard entries pagination, improved search empty-state feedback, and smarter default entry date behavior.
- Preserved month/year/page context after editing or deleting entries in the dashboard.
- Improved recurring processing to backfill all missed occurrences instead of only one per visit.
- Hardened server-side validation (including empty goal name protection and reused finance validators).
- Improved visual consistency (card hover behavior, value color class mapping, negative balance highlight).
- Improved operational robustness: PDF export fully in-memory and explicit backup messaging for non-SQLite databases.

### 2026-03-12 (1.2.0)

- Hardened authentication and recovery flows with rate limiting, temporary account lockout, generic recovery responses, and stronger session handling.
- Improved reliability with recurring maintenance outside the request cycle, safer SQLite backup generation, a health endpoint, and broader runtime protections.
- Reduced duplication by moving auth/profile, validation, ownership, catalogs, and recurring logic into dedicated services.
- Upgraded UX with dynamic page titles, better loading and empty states, confirmation modal flow, mobile/navigation polish, and accessibility improvements.
- Added enterprise-grade quality gates with CI, CodeQL, Ruff, pre-commit, dependency auditing, expanded test coverage, and release/rollback guidance.

### 2026-03-16 (1.3.0)

- Introduced the `Meu Perfil` hub with recovery key controls, managed backups, login sessions, activity history, and system status.
- Added automatic backup routines with retention policy and persisted backup history.
- Added the guided update system on `/about`, including version checks, pre-update backup, safe package apply flow, and migration execution.
- Expanded the finance domain with category and subcategory hierarchy plus payment/receiving method support across create, edit, import, export, and reports.
- Improved top navigation behavior and mobile layout polish.
- Expanded observability with audit events for core business actions and richer operational status visibility.

### 2026-07-13 (1.4.0)

- Added a dedicated desktop runtime profile with debug disabled, Waitress serving on localhost, and a cookie policy compatible with local HTTP.
- Moved desktop database, logs, backups, updates, profile images, and the persisted local secret to the user's local application-data directory.
- Replaced the deterministic local secret fallback with an encrypted, randomly generated secret that survives application upgrades.
- Included migrations, the update manifest, the version file, and the complete multi-size Windows icon in packaged builds.
- Updated vulnerable runtime dependencies and restored the Bandit security scan on Python 3.14.
- Completed and rebuilt Portuguese, English, and Spanish catalogs with validated placeholders and no fuzzy or missing entries.
- Refined dashboard wording, singular/plural item counts, and dark-mode chart contrast.
- Bundled all frontend runtime assets so the installed application works without internet access.
- Added single-instance enforcement, safe migration of legacy 1.3 desktop data, and an installer-based update flow with SHA-256 validation.
- Added GitHub Release automation with checksums, release metadata, update manifest, and build provenance attestation.
- Fixed packaged database migrations, added a dedicated Windows shortcut icon, and hardened reinstall/uninstall cleanup for running Finora processes.

### 2026-07-20 (1.4.1)

- Made the new/edit entry modal scroll within compact desktop windows so every field and action remains accessible.
- Preserved the modal header and action footer while the long form content scrolls naturally with mouse, touchpad, touch, and keyboard.
- Simplified Windows distribution and in-app updates around official HTTPS downloads, SHA-256 verification, pre-update backups, and GitHub provenance attestations.
- Updated the executable, installer, update manifest, release metadata, documentation, and automated release pipeline for version 1.4.1.

### 2026-07-20 (1.4.2)

- Fixed in-app updates failing with `Permission denied` when WebView2 kept its runtime `lockfile` open.
- Excluded transient WebView2 storage, instance locks, runtime state, and temporary files from pre-update backups while preserving the database, local mail settings, and profile images.
- Added regression coverage that simulates a locked WebView2 file during the desktop update flow.
- Documented the one-time manual installer path required for affected 1.4.0 and 1.4.1 installations.

### 2026-07-20 (1.4.3)

- Removed the visual overlay that could cover the Sessions tab icon in the horizontally scrollable profile navigation.
- Made the backup, active-session, recent-activity, and open-alert indicators accessible shortcuts to their corresponding profile areas.
- Added totals and breakdowns for sessions, activity types, and system failures while retaining pagination for all histories.
- Added secure deletion of ended session records, user-owned activity records, and user-owned system events, with CSRF protection and confirmation prompts.
- Corrected the navigation breakpoint to prevent horizontal page overflow on compact desktop and tablet-sized windows.
- Expanded regression coverage for profile navigation, pagination, ownership boundaries, active-session protection, counters, and deletion flows.

### 2026-07-20 (1.4.4)

- Added bank accounts, savings accounts, wallets, credit cards, investments, per-account balances, and a consolidated balance.
- Added internal transfers that move balances without being counted as income or expenses.
- Added OFX statement import, reusable CSV/XLSX column profiles, duplicate detection, and bank reconciliation with existing or newly created entries.
- Redefined dashboard indicators around realized balance, projected balance, received income, paid expenses, receivables, and payables.
- Added income-by-category alongside expenses-by-category and a persistent collapsible analytics rail that expands the monthly entries workspace.
- Added meaningful icons to the primary navigation and introduced Accounts immediately after Dashboard.
- Localized system failure types and hardened long-content wrapping across cards, status panels, badges, lists, and operational surfaces.
- Added an Alembic migration and regression coverage for account ownership, balances, transfers, imports, reconciliation, dashboard calculations, and responsive UI contracts.

### 2026-07-21 (1.4.5)

- Made automatic updates resilient to intermittent GitHub, SSL handshake, and read timeouts with separate download limits, controlled retries, and progressive backoff.
- Downloads are now written to a temporary partial file and moved atomically only after completion; previously verified installers are reused safely through SHA-256 validation.
- Replaced raw SSL diagnostics with clear, actionable connection guidance and corrected loading-state recovery around confirmed update actions.
- Added a polished donation area to the About page with secure PayPal access, copyable PIX key, accessible feedback, recipient transparency, and visually normalized QR Codes.
- Added regression coverage for transient timeouts, retry exhaustion, atomic installer downloads, partial-file cleanup, and donation security/accessibility contracts.

## 👥 Authors

- INformigados: https://github.com/informigados/
- Alex Brito: https://github.com/alexbritodev

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
