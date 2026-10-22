# Changelog

## [20.0.1.1.1] - 2026-10-22

### Added

- **`requirements.txt` ships inside the module folder**, so the store download includes the Python dependencies. The repository-root file now includes it with `-r`. It adds `packaging`, which Odoo 20 needs to check versioned `external_dependencies`.
- **Installation and server-limit guidance on the app page and in the README**: installing the requirements on self-hosted servers and on Odoo.sh (which only reads requirements files in the folder that contains the module), and the recommended `odoo.conf` memory and time limits for large databases.
- Regression coverage aligned with 19.0 for the filestore option, corrupt ZIP members, `pg_dump` failures, reader permissions, partial-upload warnings and the scheduler's filestore selection.

### Fixed

- PostgreSQL dump jobs are always created without the filestore flag, including jobs created outside a backup configuration, as on 19.0.
- The failure-notification help now mentions partial storage failures, and the AsyncSSH install hint includes the `<2.24` cap.

### Changed

- **Minimum AsyncSSH version in `external_dependencies`** (`asyncssh>=2.21.0`): Odoo now refuses to install or upgrade the module (including `-u all`) while it is missing or older. The `<2.24` upper bound stays in `requirements.txt` only.
- Store page: restored the release category chips, corrected the footer version and removed provider images that the page did not use.

### Upgrade notes

- Install the updated `requirements.txt` (including `packaging`) before upgrading the module; otherwise Odoo blocks the upgrade with a message naming the missing library.

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
