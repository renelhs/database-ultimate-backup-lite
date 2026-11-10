# Changelog

## [20.0.1.1.5] - 2026-11-10

### Security

- **Neutralized copies drop the SFTP password**: Odoo reads `data/neutralize.sql` when it neutralizes a database (`odoo-bin neutralize`, or a restore or duplication with "Neutralize" in the database manager). The SFTP password is now cleared there, so a copy of production can no longer upload to, list or delete from the production SFTP server. Odoo runs that file before any module upgrade, so only the columns that exist in the copy are cleared and databases from earlier versions are neutralized too.

### Upgrade notes

- No database change and no new Python dependency.
- After neutralizing a database, its SFTP destinations remain without their password. To back up that copy, enter the password again, preferably for a separate server.
- Destinations that authenticate with the SSH keys of the Odoo server's system user are not affected: those keys are not stored in the database, so a copy running on the same server can still connect with them.

## [20.0.1.1.4] - 2026-11-09

### Fixed

- **Temporary files of interrupted backups are freed before the next backup**: when a scheduled action passes its time limit in threaded mode (`workers = 0`), Odoo reloads itself with `execv` and keeps its PID (PID 1 in a container). The stale sweep only compared PIDs, so it took the leftover of the stopped backup, often several GB in `/tmp`, for a running backup and kept it for up to 24 hours; each retry added another copy until the disk was full ("No space left on device"). Temporary folders now also record a token drawn when Odoo starts (and again in each prefork worker), the host and PID namespace, and the process start time. The sweep removes the folder of a stopped, reloaded or reused-PID process at once, and never removes the folder of a running backup, however long it runs. Folders from another host or container sharing the temporary directory are only removed after 24 hours.
- **Backups whose Odoo process stops are no longer started every minute forever**: a stop (time limit, memory limit, restart) left no error behind, so the job went back to the queue and ran again a minute later, reloading Odoo each time without any notification. Each attempt is now saved before the backup starts. A stopped backup is started once more; after two stopped attempts it is marked as failed and the failure notification is sent, naming the time limit Odoo applies (`limit_time_real_cron`, or `limit_time_real` while `limit_time_real_cron` is `-1`) and how to raise it. Backups that fail with an error, such as a full disk, are still not retried.

### Changed

- **Running backups show as Running**: the status is saved when a backup starts. The job form shows a notice while it runs and the number of attempts after a retry.

### Upgrade notes

- No new Python dependency. Upgrade the module to add the attempt counter to backup jobs.
- Folders left by earlier versions only record a PID: they are removed after 2 hours, or 24 hours while that PID belongs to another running process. To reclaim the space at once, delete `/tmp/odoo_backup_*` while no backup is running.
- A backup that takes longer than Odoo's limit for scheduled actions is stopped twice and then reported. Set `limit_time_real_cron` in `odoo.conf` well above the time your backups take (see "Odoo Configuration for Large Databases" in the README).

## [20.0.1.1.3] - 2026-11-05

### Changed

- **Dropbox and Microsoft OneDrive named in the Full edition links**: the information box in the Storage Providers section, the store summary, the edition comparison on the app page and the README now list Dropbox and OneDrive among the destinations of Database Ultimate Backup, which added them in 20.0.1.3.0.

## [20.0.1.1.2] - 2026-11-04

### Changed

- **Link to the Full edition in the configuration**: the Storage Providers section of a backup configuration shows an information box pointing to Database Ultimate Backup on Odoo Apps for Amazon S3, Google Drive, Azure, Odoo.sh or encryption. The note under the providers now only states what the Lite supports.
- **Store title**: the app is listed as "Database Ultimate Backup Lite: Free Auto Backup to Local & SFTP", and the summary names the destinations and email alerts.

## [20.0.1.1.1] - 2026-10-22

### Added

- **`requirements.txt` ships inside the module folder**, so the store download includes the Python dependencies. The repository-root file now includes it with `-r`. It adds `packaging`, which Odoo 20 needs to check versioned `external_dependencies`.
- **Installation and server-limit guidance on the app page and in the README**: installing the requirements, and the recommended `odoo.conf` memory and time limits for large databases.
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
