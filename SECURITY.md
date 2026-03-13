# 🔐 Security Policy

Finora is a local-first personal finance application. Security issues can affect private financial records, authentication flows, backups, and imported files, so please report them responsibly.

## 🛡️ Supported Versions

| Version | Supported |
| --- | --- |
| `1.1.x` | ✅ Yes |
| `1.0.x` | ❌ No |
| `< 1.0` | ❌ No |

Only the latest stable release line receives security fixes.

## 🚨 Reporting a Vulnerability

Please **do not open a public issue, pull request, or discussion** for a suspected vulnerability.

Preferred reporting path:

1. Use GitHub private vulnerability reporting for this repository, if it is enabled.
2. If private reporting is not available, contact the maintainers privately through the GitHub profiles listed in [README.md](README.md).

Please include as much of the following as possible:

- A short description of the issue and the affected area.
- The Finora version and how you are running it (`development`, `production`, SQLite, MySQL, etc.).
- Clear reproduction steps.
- Expected behavior and actual behavior.
- Security impact assessment.
- Proof of concept, logs, or screenshots when relevant.
- Whether secrets, user data, backups, or authentication flows may be exposed.

## ⏱️ Response Expectations

- We aim to acknowledge new reports within **5 business days**.
- We may ask follow-up questions to confirm impact or reproduction details.
- We will try to prepare a fix and coordinate disclosure before public discussion.
- If the report is not reproducible or is outside project scope, we will explain why.

## 🔒 Security Controls Already Present

Finora already includes several baseline protections:

- 🧩 CSRF protection for form and JSON flows.
- 🍪 Hardened cookie settings, including `HttpOnly` and `SameSite=Lax`, with `Secure` cookies in production.
- 🔑 `SECRET_KEY` is required in production mode.
- 🕒 Password reset tokens expire after **1 hour**.
- 🔐 Password strength validation is enforced in authentication flows.
- 📏 Import limits are enforced for file size and row count.
- 🖼️ Profile image uploads are size-limited and validated as image files.
- 🗃️ Backup export is restricted to supported local database scenarios and warns when file backup is not appropriate.
- 🌐 The built-in server flow binds to `127.0.0.1`, reducing accidental LAN exposure in default usage.

## ✅ Deployment and Hardening Notes

If you deploy or distribute Finora, please also follow these practices:

- Use a strong, unique `SECRET_KEY`.
- Prefer a managed production database instead of local SQLite for shared or long-lived deployments.
- Never commit `.env`, database files, exports, backups, generated profile images, or credentials.
- Keep dependencies updated and review security-sensitive changes before release.
- Review changes to authentication, imports, exports, backup, and profile upload flows with extra care.

## 🙏 Scope Notes

The following are generally **not** considered security vulnerabilities by themselves:

- Missing best-practice headers in a local-only development setup.
- Issues that require direct local filesystem access already granted to the attacker.
- Problems caused by intentionally insecure local configuration values such as weak development secrets.

When in doubt, report privately anyway. A low-confidence report is better than a silent one.
