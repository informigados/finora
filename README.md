# 💼 Finora

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.x-black)
![Database](https://img.shields.io/badge/database-sqlite%20%7C%20mysql-0f766e)
![License](https://img.shields.io/badge/license-MIT-green)

Finora is a local-first personal finance application built with Flask.  
It provides expense/income tracking, recurring entries, budgets, goals, imports/exports, backups, profile management, and multilingual UI.

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

## 🗄️ Database Notes

- Default database: `database/finora.db`
- Production recommendation: managed MySQL or PostgreSQL
- Set database URL through `DATABASE_URL`

Example MySQL URL:

```ini
DATABASE_URL=mysql+pymysql://user:password@host:3306/finora
```

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

## 👥 Authors

- INformigados: https://github.com/informigados/
- Alex Brito: https://github.com/AlexBritoDEV

## 📜 License

MIT
