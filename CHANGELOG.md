# Changelog

All notable changes to the Database Ultimate Backup Lite module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [16.0.1.1.1] - 2026-06-26

### Changed

- **Odoo.sh is now explicitly unsupported**: the module documentation and store
  description now state that Lite backups run on On Premise only — Odoo Online
  (SaaS does not allow third-party modules) and Odoo.sh are not available. A new
  *Platform Availability* section in the store description makes this clear up
  front.

### Fixed

- **Fail fast on Odoo.sh instead of producing an empty backup**: Odoo.sh revokes
  the tenant role's read access to `pg_settings` (CVE-2024-7348 hardening), so
  `pg_dump` aborts and previously left a silently empty/corrupt dump. Backups now
  detect Odoo.sh (via the platform's `backup.daily` directory) and stop with a
  clear, actionable error pointing to Database Ultimate Backup (Full), which
  ships native Odoo.sh backup support. Self-hosted/On-Premise behaviour is
  unchanged.

---

## [16.0.1.1.0] - 2026-06-01

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

## [16.0.1.0.0] - 2026-02-26

### Initial Release for Odoo 16.0

Complete backup solution for Odoo 16.0 with local and SFTP remote storage.

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

#### SFTP Remote Storage Provider
- **Remote Backup Storage**: Securely transfer backups to any SSH/SFTP server
- **High-Performance Transfers**: Powered by AsyncSSH for fast, reliable uploads
- **Password Authentication**: Simple password-based SFTP authentication
- **Automatic Directory Creation**: Optionally create remote directories on the fly
- **Upload Verification**: Automatic file size verification after transfer
- **Configurable Timeouts**: Connection and transfer timeout settings
- **File Permission Preservation**: Optionally preserve file permissions during transfer
- **Remote Backup Management**: List, download, and delete backups on remote servers
- **Disk Space Monitoring**: Remote server disk space information

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
