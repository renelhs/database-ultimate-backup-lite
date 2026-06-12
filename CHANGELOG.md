# Changelog

All notable changes to the Database Ultimate Backup Lite module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [19.0.1.3.0] - 2026-06-12

### Security

- **SFTP host key verification (trust on first use)**: SFTP connections
  previously ran with `known_hosts=None`, i.e. no server identity check at
  all, leaving backups exposed to man-in-the-middle interception. The provider
  now pins the server's public host key automatically on the first successful
  connection and validates every subsequent connection against it — no extra
  configuration or `known_hosts` file required, so first-time setup is
  unchanged.

### Added

- **`Verify Server Host Key` toggle** (default: enabled) on the SFTP provider,
  plus a read-only **Host Key Fingerprint** (SHA-256) shown under
  *Connection Settings → Host Key Security*. The fingerprint can be checked
  against `ssh-keyscan <hostname>` run on a trusted machine.
- **`Reset Pinned Host Key` button** (with confirmation) for the legitimate
  case where the SFTP server was reinstalled or migrated and its host key
  changed.
- **Actionable host-key mismatch errors**: connection, upload, download and
  delete operations now report an explicit security warning — including the
  pinned fingerprint and the reset procedure — instead of the raw asyncssh
  "Host key is not trusted" error.
- **Test Connection** result now reports the host key status
  (pinned / verified / verification disabled).

### Fixed

- **Stale-temp sweep could delete the working directory of a long-running
  backup**: the hourly sweep (and the sweep at the start of every run)
  removed any `/tmp/odoo_backup_*` dir older than 2 hours — including the
  temp dir of a backup *still in progress* on a large database, corrupting
  the archive mid-write with no error trail. Every temp dir now records its
  owner process PID in a `.odoo_backup_owner` marker; the sweep only removes
  dirs whose owner process is gone (SIGKILL, OOM, restart), so a backup can
  legitimately run for many hours without being swept out from under the
  worker. A 24-hour hard cap still bounds leakage in the pathological case
  where a recycled PID matches an unrelated live process. Dirs created by
  older versions of the module (no marker) keep the previous age-based
  cleanup.

### Notes

- Existing SFTP providers pin their server's key on the next successful
  connection or backup run; no manual action is needed after upgrading.

---

## [19.0.1.2.0] - 2026-06-01

### Reliability & Large-Database Performance

Hardening pass focused on backups of large databases and on never leaving
temporary files stranded under `/tmp`.

### Changed

#### Backup engine
- **No more filestore double-copy**: the filestore is now streamed straight
  into the backup archive from its live location instead of being copied into
  a temp directory first. This removes the peak doubled disk footprint that
  could exhaust `/tmp` on large databases.
- **Lower CPU usage on large filestores**: filestore entries are stored
  uncompressed (they are already-compressed binaries — images, PDFs, etc.),
  while `dump.sql` and `manifest.json` stay compressed. This prevents the cron
  worker from exhausting `limit_time_cpu` and being killed mid-archive on big
  databases. Archives remain fully restore-compatible.
- **ZIP64 enabled**: filestores larger than 4 GiB now archive correctly.
- **Robust temp-dir cleanup**: each run owns its temporary directory end-to-end
  and always cleans it up, logging (instead of silently swallowing) any cleanup
  failure.

### Added
- **Hourly stale temp sweep**: a new scheduled job removes leftover
  `odoo_backup_*` temp directories stranded by a killed worker, an Odoo restart
  mid-backup, or a cleanup failure under disk pressure.
- **Friendlier error messages**: common failures (disk full, permission denied)
  are reported as clear, actionable messages instead of raw tracebacks.
- **Human-readable duration**: backup jobs now show duration as e.g. "1h 2m 15s".
- **Sub-MB backup size precision**: backup size is stored with decimal precision.

### Fixed
- Corrected status colour decorations on the Recent Backup Jobs list in the
  configuration form (were keyed off obsolete status values and never applied).

---

## [19.0.1.1.0] - 2026-02-10

### SFTP Remote Storage Support

Added SFTP/SSH remote storage provider, making the Lite edition a truly functional
off-site backup solution.

### Added

#### SFTP Storage Provider
- **Remote Backup Storage**: Securely transfer backups to any SSH/SFTP server
- **High-Performance Transfers**: Powered by AsyncSSH for fast, reliable uploads
- **Password Authentication**: Simple password-based SFTP authentication
- **Automatic Directory Creation**: Optionally create remote directories on the fly
- **Upload Verification**: Automatic file size verification after transfer
- **Configurable Timeouts**: Connection and transfer timeout settings
- **File Permission Preservation**: Optionally preserve file permissions during transfer
- **Remote Backup Management**: List, download, and delete backups on remote servers
- **Disk Space Monitoring**: Remote server disk space information

#### Configuration Updates
- SFTP providers can now be assigned to backup configurations alongside local providers
- New SFTP Storage menu under Storage Providers
- Updated backup configuration form with SFTP provider selection

### Changed
- Module now requires `asyncssh` Python package (`pip install asyncssh`)
- Updated module description to reflect SFTP capabilities

---

## [19.0.1.0.0] - 2026-02-06

### Initial Release (Lite Edition)

Free local backup solution for Odoo 19.0 - zero external dependencies.

### Added

#### Core Features
- **Backup Configuration Model**: Create and manage multiple backup configurations
- **Backup Job Model**: Track individual backup executions with detailed monitoring
- **Multiple Backup Formats**: Support for ZIP archives (with filestore) and PostgreSQL dumps
- **Automated Scheduling**: Cron-based scheduled backups with configurable intervals
- **Manual Backup Execution**: On-demand backup creation via UI button

#### Local Storage Provider
- Store backups on local filesystem or network-mounted drives
- Directory organization with date-based folders
- Disk space checking and monitoring
- Integrity verification
- Storage information display

#### Advanced Features
- **Backup Verification**: Automatic integrity checking of backup files
- **Flexible Retention Policies**: Keep last N backups or retain for N days
- **Automated Cleanup**: Automatic removal of old backups based on retention policy
- **Email Notifications**: Configurable notifications for backup success/failure
- **Custom Filename Templates**: Customize backup filenames with variables

#### Monitoring & Statistics
- **Backup Job History**: Complete history of all backup operations
- **Success Rate Tracking**: Monitor backup reliability over time
- **Detailed Job Information**: Duration, file size, status, error messages
- **Provider-specific Results**: Track upload results for each storage provider

#### Security & Access Control
- **Two-tier User Groups**: User (read-only) and Administrator (full access)
- **Model-level Access Rules**: Granular permissions per model and operation
- **System User**: Dedicated user for automated cron operations

---

## Need Multi-Cloud Storage?

Upgrade to **Database Ultimate Backup** (Full) for enterprise multi-cloud support:
- AWS S3, Azure Blob Storage, Google Cloud Storage
- DigitalOcean Spaces
- Parallel uploads to multiple providers simultaneously
- Server-side encryption (AES256, KMS)
- Multi-cloud redundancy

---

## Support

For bug reports, feature requests, or questions:
- **GitHub**: https://github.com/renelhs
- **Email**: reneluishs@gmail.com

## License

This module is licensed under MIT. See LICENSE file for details.

---
