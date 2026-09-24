# -*- coding: utf-8 -*-
{
    'name': "Database Ultimate Backup Lite",

    'summary': "Free automated database backups with Local + SFTP storage, retention policies, integrity verification, and monitoring",

    'description': """
        Database Ultimate Backup Lite - Free Backup Solution with Local & SFTP
        ======================================================================

        A free, reliable database backup solution for Odoo 20.0 with local and SFTP
        remote storage, automated scheduling, retention policies, and comprehensive monitoring.

        Core Features
        -------------
        * **Local Storage**: Store backups on local filesystem or network-mounted drives
        * **SFTP Remote Storage**: Securely transfer backups to remote servers via SSH/SFTP
        * **Backup Formats**: ZIP archives with or without filestore, or PostgreSQL dumps
        * **Integrity Verification**: Automatic verification after backup creation
        * **Flexible Scheduling**: Automated backups via configurable cron jobs
        * **Retention Policies**: Keep last N backups or retain for N days
        * **Automated Cleanup**: Automatic removal of old backups based on policy
        * **Job Monitoring**: Track backup history, status, duration, and file sizes
        * **Email Notifications**: Get notified on backup success or failure
        * **Success Rate Tracking**: Monitor backup reliability over time

        SFTP Provider Features
        ----------------------
        * High-performance transfers powered by AsyncSSH
        * Password-based authentication
        * Automatic remote directory creation
        * Upload verification (size check)
        * Configurable connection and transfer timeouts

        Security Features
        -----------------
        * Two-tier access control: User and Administrator roles. Creating a
          database dump requires the Backup Administrator group (or the backup
          cron user); read-only Backup Users cannot trigger dumps.
        * Secure credential storage
        * Granular model-level permissions

        Security Note: list_db and database dumps
        -----------------------------------------
        The module uses an internal dump routine compatible with Odoo 20's
        ``odoo.modules.db.dump``. A full database dump can still be produced
        when ``list_db = False`` is set in ``odoo.conf``. Access is enforced
        by requiring the Backup Administrator group, so setting
        ``list_db = False`` alone is not sufficient to prevent dumps via this
        module — restrict membership of the backup administrator group
        accordingly.

    """,

    'author': "René Hechavarría",
    'website': "https://github.com/renelhs",
    'maintainer': "René Hechavarría",
    'support': "reneluishs@gmail.com",

    'category': 'Administration',
    'version': '20.0.1.0.0',

    # Module dependencies
    'depends': ['base'],

    # External dependencies
    'external_dependencies': {
        'python': ['asyncssh'],
    },

    # Data files
    'data': [
        # Security
        'security/backup_security.xml',
        'security/ir.access.csv',

        # Data
        'data/backup_cron.xml',
        'data/backup_provider_data.xml',

        # Views
        'views/backup_config_views.xml',
        'views/backup_job_views.xml',
        'views/backup_provider_views.xml',
        'views/menus.xml'
    ],

    'installable': True,
    'auto_install': False,
    'application': True,

    'license': 'Other OSI approved licence',

    # Store metadata
    'price': 0,
    'currency': 'USD',

    # Images
    'images': [
        'static/description/banner.png',
    ],
}
