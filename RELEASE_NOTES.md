## Finora 1.4.6

### Highlights

- Hardened financial input validation and corrected international amount parsing in imports.
- Restricted bank reconciliation to paid, compatible entries in the same account and prevented entry reuse. Changes to an entry's amount, type, status, or account now reopen reconciliation.
- Fixed dialog and overlay positioning. Long forms now scroll internally in compact windows while keeping actions accessible.
- Improved label associations in account forms and accessible naming for profile deletion confirmation.
- Fitted PDF tables within page margins and bundled Unicode fonts for offline reports.
- Added controlled handling of invalid dashboard and export periods and updated dependencies flagged by security auditing.
- Added regression coverage for financial validation, imports, reconciliation, and PDF exports.

### Upgrade Notes

Run this release's installer to update. The installer preserves local data, and in-app updates also create a backup before installation. This release does not change the database schema.
