# Changelog

All notable changes to the Database Ultimate Backup Lite module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [17.0.1.0.0] - 2026-02-26

### Initial Release for Odoo 17.0

Complete backup solution for Odoo 17.0 with local and SFTP remote storage.

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
