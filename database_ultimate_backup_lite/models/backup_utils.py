"""Shared boundaries for backup permissions, paths and provider timestamps."""

import datetime
import os

from odoo.exceptions import AccessError, ValidationError


ADMIN_GROUP = 'database_ultimate_backup_lite.group_backup_admin'


def require_backup_admin(records):
    if not records.env.su and not records.env.user.has_group(ADMIN_GROUP):
        raise AccessError('Backup administrator rights are required for this operation.')
    records.check_access('write')


def validate_filename(filename):
    if (not isinstance(filename, str) or not filename or filename in ('.', '..')
            or any(char in filename for char in ('/', '\\', '\x00'))):
        raise ValidationError('A backup filename must be a name, without directory components.')
    return filename


def confined_path(root, candidate, *, allow_root=False):
    root = os.path.realpath(root)
    candidate = os.path.realpath(candidate)
    if os.path.commonpath((root, candidate)) != root or (candidate == root and not allow_root):
        raise ValidationError('The backup path must remain inside its storage directory.')
    return candidate


def utc_datetime(value):
    """Normalize SDK datetimes and Drive RFC3339 strings to Odoo's naive UTC."""
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime.datetime):
        raise ValidationError('The storage provider returned an invalid backup timestamp.')
    if value.tzinfo is not None:
        value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return value
