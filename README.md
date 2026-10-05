# Database Ultimate Backup Lite for Odoo 19.0

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Odoo Version](https://img.shields.io/badge/Odoo-19.0-brightgreen.svg)](https://www.odoo.com)
[![Price](https://img.shields.io/badge/Price-Free-green.svg)]()

A free, reliable database backup solution for Odoo 19.0 with **local and SFTP remote storage**, automated scheduling, retention policies, and comprehensive monitoring.

## Features

### Core Capabilities
- **Local Storage**: Store backups on local filesystem or network-mounted drives
- **SFTP Remote Storage**: Securely transfer backups to remote servers via SSH/SFTP
- **Backup Formats**: ZIP archives with or without filestore, or PostgreSQL custom dumps
- **Integrity Verification**: ZIP CRC checks, nonempty SQL validation, complete PostgreSQL archive parsing, and a recorded SHA-256 checksum
- **Flexible Scheduling**: Manual and scheduled requests are queued for a dedicated backup worker

### Advanced Management
- **Retention Policies**: Keep last N backups or retain for N days
- **Automated Cleanup**: Automatic removal of old backups based on retention policy
- **Job Monitoring**: Track backup history, status, duration, and file sizes
- **Email Notifications**: Get notified on backup success/failure
- **Success Rate Tracking**: Monitor backup reliability over time

### Local Storage Provider
- Store backups on local filesystem or network-mounted drives
- Disk space checking and monitoring
- Integrity verification
- Organized directory structure with date-based folders

### SFTP Storage Provider
- High-performance transfers powered by AsyncSSH
- Password-based authentication
- Automatic remote directory creation
- Upload verification (file size check)
- Configurable connection and transfer timeouts
- Remote disk space monitoring

### Security
- Two-tier access control (User and Administrator)
- Granular model-level permissions
- System user for automated operations
- Administrator-only access to SFTP passwords and transfer operations
- Local paths confined to the configured storage directory; verified uploads are published atomically with private file permissions

Credentials are protected by Odoo access permissions; the module does not encrypt them in the database. ZIP/dump validation and checksums detect archive problems but do not replace a restore test. SFTP upload verification compares file sizes.

### Upgrading to 19.0.1.6.0

Upgrade the module to create its Job Queue scheduled action, and keep Odoo cron workers running for manual and scheduled backups. The upgrade preserves the existing configuration and filestore choices. Review the configured limits: the local directory maximum (100 GB by default) and SFTP transfer timeout (3600 seconds by default) are now enforced; `0` disables either limit. Keep job history so retention can identify recorded copies. Odoo 19's Python 3.10 minimum and the `asyncssh<2.24` dependency remain supported.

## Installation

### 1. Install Dependencies

```bash
pip install "asyncssh<2.24"
```

### 2. Install the Module

1. Copy the `database_ultimate_backup_lite` folder to your Odoo addons directory
2. Update the apps list: Go to Apps > Update Apps List
3. Search for "Database Ultimate Backup Lite"
4. Click Install

### 3. Configure Permissions

Assign users to backup groups:
- **Settings > Users & Companies > Users**
- Select a user and go to the "Database Backup" tab
- Assign appropriate group:
  - **User**: View backup configurations and jobs (read-only access)
  - **Administrator**: Full access to create, modify, and execute backups

## Quick Start Guide

### Step 1: Configure a Storage Provider

#### Option A: Local Storage

Navigate to **Database Ultimate Backup Lite > Storage Providers > Local Storage** and create a provider:

```
Name: Local Backup Server
Backup Directory: /opt/odoo/backups
Check Disk Space: Yes (recommended)
Min Free Space: 5 GB
```

#### Option B: SFTP Remote Storage

Navigate to **Database Ultimate Backup Lite > Storage Providers > SFTP Storage** and create a provider:

```
Name: Remote Backup Server
Hostname: backup.example.com
Port: 22
Username: backup_user
Password: ********
Remote Directory: /home/backups/odoo
Create Remote Directories: Yes
```

Use the **Test Connection** button to verify the provider is configured correctly.

### Step 2: Create a Backup Configuration

Navigate to **Database Ultimate Backup Lite > Backup Configurations > Create**

```
Name: Daily Production Backup
Database: [automatically populated with current database]
Backup Format: ZIP Archive
Include Filestore: Yes

Storage Providers:
- Select your local and/or SFTP storage providers

Retention Policy: Keep Last N Backups
Number of Backups to Keep: 7

Options:
- Verify Backup Integrity: Yes
- Notify on Failure: Yes

Notification Emails: admin@example.com
```

Click **Save**.

### Step 3: Test Your Configuration

1. Click the **Test Providers** button to verify all providers are accessible
2. Click **Create Backup Now** to queue a manual test backup
3. Open **Backup Jobs** and refresh to see the completed result, logs and SHA-256 checksum
4. Verify the backup file exists in your storage location

The **Database Ultimate Backup Lite Job Queue** scheduled action is enabled on installation and processes pending jobs every minute. Odoo cron workers must be running. Uploads remain sequential. Repeated requests for the same configuration are rejected while a job is pending or running; **Retry Backup** creates a new job and preserves the previous attempt.

### Step 4: Enable Automated Backups

The scheduler has a daily interval and is disabled initially. Activate it when your configuration is ready.

To customize the schedule:
1. Go to **Settings > Technical > Automation > Scheduled Actions**
2. Search for "Database Ultimate Backup Lite Scheduler"
3. Edit the **Execute Every** field to your preferred interval
4. Set the **Next Execution Date** if needed
5. Enable the scheduled action

**Active backup configurations** will automatically run according to the cron schedule.

## Configuration Reference

### Backup Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **ZIP Archive + filestore** | Database and file-backed attachments | Full system backups, recommended for production |
| **ZIP Archive without filestore** | Database packaged as ZIP, without file-backed attachments | Smaller backups when the filestore is backed up separately |
| **PostgreSQL Dump** | PostgreSQL custom-format dump, no filestore | Database-only backups |

Odoo 19's database manager can restore both ZIP backups and PostgreSQL custom dumps. Custom dumps can also be restored with `pg_restore --no-owner --dbname=restored_db backup.dump` into an empty database. Backups without the filestore cannot recover file-backed attachments; restore the matching filestore separately if needed.

**Include Filestore** is enabled by default and applies only to ZIP backups. Each job records its own selection, so changing a configuration does not rewrite the backup history. Updating from an earlier release preserves the existing ZIP-with-filestore behavior.

Only Backup Administrators can run backups, test connections, transfer or delete backup files, and read SFTP passwords. Backup Users retain read-only access to configurations and job history. A backup with failed destinations is shown as a warning and uses the failure-notification setting.

### Retention Policies

| Policy | Description | Example |
|--------|-------------|---------|
| **Keep Last N Backups** | Maintains the most recent N backups | Keep last 7 backups = 1 week of daily backups |
| **Keep for N Days** | Retains recent backups and always preserves the newest known copy | Keep 30 days, plus the latest copy if all are older |
| **Keep All Backups** | Disables automatic deletion for this configuration | Archive without automatic retention |

Retention only deletes successful uploads recorded for the current configuration and destination. Untracked files, unknown dates and ambiguous legacy locations are preserved. Keep the job history: deleting it also removes the evidence used to identify owned copies. Cleanup runs after successful or partially successful backups and through the cleanup scheduled action.

### Backup Name Template

Customize backup filenames using variables:
- `{database}` - Database name
- `{timestamp}` - Timestamp including microseconds
- `{format}` - File extension (`zip` or `dump`)

**Default**: `{database}_{timestamp}.{format}`

A unique suffix is always appended to prevent a repeated filename template from overwriting an earlier run. Partial uploads remain **Warning** and use the failure email preference, even when success emails are disabled.

## Troubleshooting

### Common Issues

**"No storage providers configured"**
- Configure at least one storage provider (Local or SFTP) before creating backups
- Ensure the provider is set to Active

**"Backup failed: disk space"**
- Check available disk space on backup destinations
- Reduce retention count or days
- Run cleanup manually to free space

**"AsyncSSH library not found"**
- Install the required dependency: `pip install "asyncssh<2.24"`
- Restart the Odoo service after installation

**"SFTP connection failed"**
- Verify hostname, port, username, and password
- Ensure the SFTP server is reachable from the Odoo server
- Check firewall rules for SSH port (default: 22)
- Use the Test Connection button to diagnose issues

**"Scheduled backups not running"**
- Verify the cron job is active: Settings > Technical > Scheduled Actions
- Check backup configuration is marked as Active
- Review system logs for cron execution errors

## Need Multi-Cloud Storage?

Upgrade to **Database Ultimate Backup** (Full Edition) for enterprise-grade multi-cloud support:

- **AWS S3** - Storage classes, encryption, versioning
- **Azure Blob Storage** - Storage tiers, geo-redundancy
- **Google Cloud Storage** - Flexible classes, KMS encryption
- **DigitalOcean Spaces** - Cost-effective cloud storage
- **Parallel Uploads** - Upload to multiple providers simultaneously
- **Server-side Encryption** - AES256 and KMS encryption

## Support

- **GitHub Issues**: https://github.com/renelhs/database-ultimate-backup-lite/issues

## License

This module is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Credits

### Author
- René Hechavarría

### Built With
- Odoo 19.0 Community/Enterprise Framework
- AsyncSSH for high-performance SFTP transfers
- Strategy design pattern for extensibility

---

**Database Ultimate Backup Lite** - Free local & SFTP backup solution for Odoo 19.0
