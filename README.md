# 💼 Finora

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.x-black)
![Database](https://img.shields.io/badge/database-sqlite%20%7C%20mysql-0f766e)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/informigados/finora/actions/workflows/ci.yml/badge.svg)](https://github.com/informigados/finora/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/informigados/finora)

Finora is a local-first personal finance application built with Flask.  
It provides expense/income tracking, recurring entries, budgets, goals, imports/exports, backups, profile management, and multilingual UI.

Current stable version: `1.2.0`

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
- Import (CSV/XLSX) with validation and row-level error handling
- Export (PDF/CSV/TXT)
- Local backup download
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

## 👤 Optional Default Test User

Finora supports an optional default user seed for local environments, including local desktop/package runs.

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

## 🗄️ Database Notes

- Default database: `database/finora.db`
- Production recommendation: managed MySQL or PostgreSQL
- Set database URL through `DATABASE_URL`

Example MySQL URL:

```ini
DATABASE_URL=mysql+pymysql://user:password@host:3306/finora
```

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

## 👥 Authors

- INformigados: https://github.com/informigados/
- Alex Brito: https://github.com/AlexBritoDEV

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
