# Database Ultimate Backup Lite

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Price](https://img.shields.io/badge/Price-Free-green.svg)]()

A free, reliable database backup solution for Odoo with **local and SFTP remote storage**, automated scheduling, retention policies, and comprehensive monitoring.

## Features

### Core Capabilities
- **Local Storage**: Store backups on local filesystem or network-mounted drives
- **SFTP Remote Storage**: Securely transfer backups to remote servers via SSH/SFTP
- **Backup Formats**: ZIP archives (with filestore) or PostgreSQL dumps
- **Integrity Verification**: Automatic verification of backup files after creation
- **Flexible Scheduling**: Automated backups via cron jobs with configurable intervals

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

## Installation

### 1. Install Dependencies

```bash
pip install asyncssh
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
Backup Format: ZIP Archive (includes filestore)

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
2. Click the **Create Backup Now** button to perform a manual test backup
3. Go to **Backup Jobs** to monitor the backup progress and results
4. Verify the backup file exists in your storage location

### Step 4: Enable Automated Backups

The module includes a scheduled action (cron job) that runs daily by default.

To customize the schedule:
1. Go to **Settings > Technical > Automation > Scheduled Actions**
2. Search for "Database Ultimate Backup Lite Scheduler"
3. Edit the **Execute Every** field to your preferred interval
4. Set the **Next Execution Date** if needed

**Active backup configurations** will automatically run according to the cron schedule.

## Configuration Reference

### Backup Formats

| Format | Description | Use Case |
|--------|-------------|----------|
| **ZIP Archive** | Complete backup including database and filestore | Full system backups, recommended for production |
| **PostgreSQL Dump** | SQL dump only, no filestore | Database-only backups, smaller file size |

### Retention Policies

| Policy | Description | Example |
|--------|-------------|---------|
| **Keep Last N Backups** | Maintains the most recent N backups | Keep last 7 backups = 1 week of daily backups |
| **Keep for N Days** | Retains backups newer than N days | Keep 30 days = monthly retention |

### Backup Name Template

Customize backup filenames using variables:
- `{database}` - Database name
- `{timestamp}` - Timestamp in YYYYMMDD_HHMMSS format
- `{format}` - File extension (zip or sql)

**Default**: `{database}_{timestamp}.{format}`

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
- Install the required dependency: `pip install asyncssh`
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

- **GitHub**: https://github.com/renelhs
- **Email**: reneluishs@gmail.com

## License

This module is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

## Credits

### Author
- René Hechavarría

### Built With
- Odoo Community/Enterprise Framework
- AsyncSSH for high-performance SFTP transfers
- Strategy design pattern for extensibility

---

**Database Ultimate Backup Lite** - Free local & SFTP backup solution for Odoo