# -*- coding: utf-8 -*-
# Copyright 2026 René Hechavarría
"""
Tests for the stale temp dir sweep (owner marker protection).

The sweep must reclaim temp dirs left behind by killed or reloaded Odoo
processes, at once when their owner is certainly gone, while NEVER deleting
the working directory of a backup that is still running, no matter how long
it has been running.
"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

import psutil

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.database_ultimate_backup_lite.models import backup_utils


@tagged('post_install', '-at_install')
class TestTempSweep(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env['backup.job']

    def setUp(self):
        super().setUp()
        # The sweep must never inspect a real developer/server temp directory.
        sandbox = tempfile.TemporaryDirectory(prefix='dub_sweep_test_')
        self.addCleanup(sandbox.cleanup)
        tempdir = patch('tempfile.gettempdir', return_value=sandbox.name)
        tempdir.start()
        self.addCleanup(tempdir.stop)

    def _make_temp_dir(self, age_seconds, marker=None, prefix='odoo_backup_'):
        """Create a backup-prefixed temp dir aged `age_seconds`. `marker` is
        written as the owner marker: a dict as JSON, anything else as text."""
        path = tempfile.mkdtemp(prefix=prefix)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        if marker is not None:
            with open(os.path.join(path, self.Job._TEMP_OWNER_MARKER), 'w', encoding='utf-8') as fh:
                fh.write(json.dumps(marker) if isinstance(marker, dict) else str(marker))
        past = time.time() - age_seconds
        os.utime(path, (past, past))
        return path

    def _owner(self, **values):
        """Marker of this process, as `_mark_temp_dir_owner` writes it."""
        owner = {
            'pid': os.getpid(),
            'token': backup_utils.process_token(),
            'origin': backup_utils.process_origin(),
            'started': psutil.Process().create_time(),
        }
        owner.update(values)
        return owner

    def _dead_pid(self):
        """Return the PID of a process that has already exited."""
        proc = subprocess.Popen(['true'])
        proc.wait()
        return proc.pid

    def _running_child(self):
        """Start a process that outlives the test step; return it."""
        proc = subprocess.Popen(['sleep', '60'])
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        return proc

    # -- Backups that are still running --------------------------------------

    def test_running_backup_in_another_thread_is_kept(self):
        """A backup in another thread of this process wrote the marker; it is
        kept even past the hard age limit."""
        path = self._make_temp_dir(age_seconds=0)
        writer = threading.Thread(target=self.Job._mark_temp_dir_owner, args=(path,))
        writer.start()
        writer.join()
        past = time.time() - 25 * 3600
        os.utime(path, (past, past))
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(path))

    def test_running_backup_in_another_worker_is_kept(self):
        """Prefork: the owner is another live process on this host."""
        child = self._running_child()
        path = self._make_temp_dir(age_seconds=3 * 3600, marker=self._owner(
            pid=child.pid, token='other-worker', started=psutil.Process(child.pid).create_time()))
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(path))

    def test_marker_is_written_and_detected(self):
        path = self._make_temp_dir(age_seconds=0)
        self.Job._mark_temp_dir_owner(path)
        with open(os.path.join(path, self.Job._TEMP_OWNER_MARKER), encoding='utf-8') as fh:
            owner = json.load(fh)
        self.assertEqual(owner['pid'], os.getpid())
        self.assertEqual(owner['origin'], backup_utils.process_origin())
        self.assertEqual(self.Job._temp_dir_owner_state(path), 'alive')

    # -- Owners that are certainly gone: removed at once ----------------------

    def test_dir_from_before_a_reload_is_removed_at_once(self):
        """An Odoo reload re-executes the server with the same PID (PID 1 in a
        container): the marker of the previous run has another token."""
        path = self._make_temp_dir(age_seconds=60, marker=self._owner(token='before-reload'))
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_new_process_token_makes_earlier_markers_stale(self):
        """What a reload or a forked worker does: a new token for this PID."""
        path = self._make_temp_dir(age_seconds=60)
        self.Job._mark_temp_dir_owner(path)
        previous = backup_utils.process_token()
        backup_utils._renew_process_token()
        self.addCleanup(setattr, backup_utils, '_process_token', previous)
        self.assertEqual(self.Job._temp_dir_owner_state(path), 'dead')

    def test_dir_of_dead_process_is_removed_at_once(self):
        path = self._make_temp_dir(age_seconds=60, marker=self._owner(pid=self._dead_pid()))
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_dir_of_reused_pid_is_removed_at_once(self):
        """The PID now belongs to a process started later than the owner."""
        child = self._running_child()
        started = psutil.Process(child.pid).create_time()
        path = self._make_temp_dir(age_seconds=60, marker=self._owner(
            pid=child.pid, token='old-worker', started=started - 3600))
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_dump_dirs_are_swept_too(self):
        path = self._make_temp_dir(age_seconds=60, marker=self._owner(token='before-reload'),
                                   prefix='odoo_backup_dump_')
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    # -- Owners that cannot be checked from here: hard age limit --------------

    def test_dir_of_another_container_waits_for_the_hard_limit(self):
        """Containers sharing a temp dir each have a PID 1: a marker from
        another host or PID namespace is never judged by its PID."""
        foreign = self._owner(origin='another-replica pid:[1]', token='other-container')
        recent = self._make_temp_dir(age_seconds=3 * 3600, marker=foreign)
        expired = self._make_temp_dir(age_seconds=25 * 3600, marker=foreign)
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(recent))
        self.assertFalse(os.path.exists(expired))

    def test_pid_only_marker_of_running_process_waits_for_the_hard_limit(self):
        """Markers of earlier versions hold only a PID; a running one may be a
        reused PID, so the hard limit bounds the leak."""
        child = self._running_child()
        recent = self._make_temp_dir(age_seconds=3 * 3600, marker=child.pid)
        expired = self._make_temp_dir(age_seconds=25 * 3600, marker=child.pid)
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(recent))
        self.assertFalse(os.path.exists(expired))

    # -- No usable marker: normal age limit -----------------------------------

    def test_recent_dir_without_marker_is_kept(self):
        """Also covers the instant between mkdtemp and the marker write."""
        path = self._make_temp_dir(age_seconds=60)
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(path))

    def test_old_dir_without_marker_is_removed(self):
        """Dirs created by a pre-marker version of the module fall back to
        pure age-based cleanup."""
        path = self._make_temp_dir(age_seconds=3 * 3600)
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_unreadable_marker_uses_the_normal_age_limit(self):
        recent = self._make_temp_dir(age_seconds=60, marker='{not json')
        old = self._make_temp_dir(age_seconds=3 * 3600, marker='{not json')
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(recent))
        self.assertFalse(os.path.exists(old))

    def test_pid_only_marker_of_this_pid_uses_the_normal_age_limit(self):
        """This process writes tokens, so a PID-only marker with its PID is
        from before a restart: this is the leftover of a reload in a container
        upgraded from an earlier version."""
        recent = self._make_temp_dir(age_seconds=60, marker=os.getpid())
        old = self._make_temp_dir(age_seconds=3 * 3600, marker=os.getpid())
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(recent))
        self.assertFalse(os.path.exists(old))

    def test_pid_only_marker_of_dead_process_uses_the_normal_age_limit(self):
        dead = self._dead_pid()
        recent = self._make_temp_dir(age_seconds=60, marker=dead)
        old = self._make_temp_dir(age_seconds=3 * 3600, marker=dead)
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(recent))
        self.assertFalse(os.path.exists(old))
