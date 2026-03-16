# 🤝 Contributing to Finora

Thanks for contributing to Finora. This project is a local-first personal finance application built with Flask, with focus on reliability, readable code, and practical UX.

This guide keeps contributions aligned with the current repository structure, the existing `README.md`, and the shipping behavior of the app.

## ✨ What Helps Most

Contributions are especially useful when they improve:

- Authentication and account flows
- Dashboard, entries, budgets, and goals
- Import/export reliability
- Backups and data safety
- Update delivery and release safety
- Accessibility and responsive UI
- Internationalization and translation quality
- Tests, validation, and maintainability

## 🧰 Local Setup

Use the same setup documented in [README.md](README.md):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
```

Create a local `.env` file:

```ini
SECRET_KEY=change_me
FLASK_ENV=development
# Optional:
# DATABASE_URL=sqlite:///database/finora.db
```

Apply migrations and run the app:

```powershell
flask db upgrade
python app.py
```

If your change touches migrations, also verify that `flask db upgrade` works on a fresh local database without any manual bootstrap steps.

Helper scripts are also available:

- `.\run_app.bat`
- `.\run_tests.bat`

Optional but recommended quality hook setup:

```powershell
pre-commit install
```

## 🧭 Development Guidelines

Please keep changes consistent with the current architecture:

- Put reusable business rules in `services/` when they do not belong directly in a route.
- Keep route handlers focused on request/response flow.
- Preserve server-side validation even when the UI also validates.
- Reuse existing project patterns before introducing a new abstraction.
- Keep user-facing text compatible with Flask-Babel and existing translation flow.
- Prefer focused pull requests over broad refactors.

## 🌍 Translations

Finora ships with Portuguese, English, and Spanish.

If you change user-facing strings:

1. Update the extraction catalog.
2. Update the translation files.
3. Compile translations before final verification.

Commands already used in this repository:

```powershell
pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d translations
pybabel compile -d translations
```

## 🧪 Testing Expectations

Run the test suite before opening a PR:

```powershell
python -m pytest tests -q
```

For changes that touch application code, also run:

```powershell
ruff check .
bandit -q -r app.py config.py database models routes services extensions.py
pip-audit -r requirements.txt
```

Please add or update tests when your change affects:

- Authentication or session behavior
- Imports, exports, or backups
- Update checks, package application, or migration-triggering flows
- Goals, budgets, recurring entries, or dashboard calculations
- Validation and error handling
- Migrations or persistence behavior

If a change is hard to cover with automated tests, include a short manual verification note in the PR.

## 🗃️ Database and Migrations

If you change models or persistence behavior:

- Create and validate an Alembic migration.
- Make sure existing data paths still behave safely.
- Avoid breaking local SQLite users silently.
- Call out migration impact clearly in the PR description.

## 🪵 Logging

- Production writes rotating logs to `logs/finora.log` by default.
- Preserve `request_id` in log formatting so incidents can be traced across requests.
- If you change startup, logging, or scheduler behavior, verify both terminal output and file log output.

Finora already contains compatibility handling for some legacy SQLite scenarios, but contributors should still prefer proper migrations over runtime workarounds.

## 🔐 Security-Sensitive Contributions

Changes involving login, password reset, recovery keys, profile uploads, imports, exports, cookies, sessions, backup behavior, or the update system should be reviewed with extra care.

For those changes, please include:

- What risk the change addresses
- What validation was added or preserved
- What tests were run
- Whether any documentation needs to change in `README.md` or `SECURITY.md`

## 🌿 Branches, Commits, and Pull Requests

Recommended workflow:

1. Create a branch from `main`.
2. Keep commits small and descriptive.
3. Open a PR with a clear summary and test evidence.

Good PRs usually include:

- A concise problem statement
- A short summary of the solution
- Screenshots or GIFs for UI changes
- Notes about migrations, translations, or breaking behavior
- Test results

Commit style does not need to be rigid, but clear messages help a lot. Short prefixes such as `feat:`, `fix:`, `refactor:`, `test:`, and `docs:` are welcome.

## 🚫 Do Not Commit

Please do not commit local-only or sensitive artifacts such as:

- `.env` files and secrets
- Local database files
- Exported backups and generated reports
- Uploaded profile images
- Build and distribution artifacts unless the change explicitly targets packaging/release assets

The repository already ignores many of these paths through `.gitignore`; still, verify your diff before pushing.

## 📝 Documentation

Update documentation when behavior changes in a user-visible or operationally important way.

This usually means updating one or more of:

- `README.md`
- `BUILD.md`
- `SECURITY.md`
- Inline comments only when they add real technical clarity

## 🙌 Final Notes

Practical contributions beat theoretical ones. A small fix with tests, migration safety, and clear docs is more valuable than a large speculative rewrite.
