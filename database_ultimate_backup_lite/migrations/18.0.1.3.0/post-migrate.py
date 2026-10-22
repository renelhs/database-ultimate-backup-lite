def migrate(cr, version):
    """Preserve the filestore policy of backups created before the selector."""
    if not version:
        return
    cr.execute("UPDATE backup_config SET include_filestore = TRUE")
    cr.execute("UPDATE backup_job SET include_filestore = (backup_format = 'zip')")
