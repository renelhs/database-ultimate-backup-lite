# Changelog

## [20.0.1.1.0] - 2026-10-04

- Queue manual and scheduled backups with protection against duplicate requests and isolated SQL failures.
- Restrict transfer helpers to internal use, enforce backup administrator permissions and validate local/SFTP filenames.
- Publish verified local uploads atomically with private permissions and enforce configured storage limits.
- Limit retention to recorded copies owned by each configuration; preserve the latest copy, unknown files and ambiguous legacy history.
- Fully validate PostgreSQL archives, reject empty SQL dumps, fail closed on local verification errors and record SHA-256 checksums.
- Apply SFTP transfer timeouts while preserving password protection and SSH host-key pinning.
- Preserve partial-success warnings and retry history, use unique filenames and avoid collisions between providers with the same name.
- Update email notifications to Odoo 20 APIs and clarify scheduling, integrity checks and retention in the documentation.
- Add regression tests for permissions, integrity, retention, queue failures, SFTP and temporary-file cleanup.

## [20.0.1.0.0] - 2026-09-24

### Initial release

- Initial release of Database Ultimate Backup Lite for Odoo 20.0.
- Automated ZIP backups with or without filestore, and PostgreSQL dump backups.
- Local and SFTP storage, integrity verification, retention policies, scheduled backups, and email notifications.
- Backup history and User/Administrator access roles.
