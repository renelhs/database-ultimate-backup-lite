"""Shared boundaries for backup permissions, paths and provider timestamps."""

import datetime
import os
import socket
import uuid

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import config


ADMIN_GROUP = 'database_ultimate_backup_lite.group_backup_admin'

# Identifies this run of the Odoo process in temp-dir owner markers. A server
# reload re-executes Odoo with the same PID (PID 1 in a container), so only a
# value drawn when the module is imported tells a previous run from this one.
_process_token = uuid.uuid4().hex


def _renew_process_token():
    global _process_token  # noqa: PLW0603
    _process_token = uuid.uuid4().hex


# Prefork workers are forked after the master imported the addons, so each
# worker draws its own token instead of sharing the master's.
if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=_renew_process_token)


def process_token():
    return _process_token


def process_origin():
    """Name the host and PID namespace in which this process's PIDs are meaningful.

    Containers sharing a temp directory each have their own PID 1, so a PID
    read from a marker is only compared when the marker has the same origin.
    """
    origin = socket.gethostname()
    try:
        origin += ' ' + os.readlink('/proc/self/ns/pid')
    except OSError:
        pass  # no PID namespaces outside Linux
    return origin


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


def cron_time_limit():
    """Return Odoo's real-time limit for a scheduled action in seconds (0: none) and its setting.

    Odoo 18 (like 19) in prefork mode (workers > 0) applies limit_time_real_cron when it
    is 0 or more (0 disables the limit) and limit_time_real when it is -1 (the
    default). In threaded mode it applies limit_time_real_cron only when it is
    above 0, so 0 does not disable the limit there.
    """
    cron_limit = config['limit_time_real_cron']
    if cron_limit > 0 or (cron_limit == 0 and config['workers']):
        return cron_limit, f"limit_time_real_cron = {cron_limit}"
    return (config['limit_time_real'] or 0,
            f"limit_time_real, applied because limit_time_real_cron is {cron_limit}")
