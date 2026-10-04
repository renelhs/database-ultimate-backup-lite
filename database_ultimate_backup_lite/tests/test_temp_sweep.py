# -*- coding: utf-8 -*-
# Copyright 2026 René Hechavarría
"""
Tests for the stale temp dir sweep (owner-PID protection).

The sweep must reclaim temp dirs left behind by killed workers while
NEVER deleting the working directory of a backup that is still running,
no matter how long it has been running.
"""
import os
import subprocess
import tempfile
import time
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTempSweep(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env['backup.job']

    def setUp(self):
        super().setUp()
        self._created = []
        # The sweep must never inspect a real developer/server temp directory.
        sandbox = tempfile.TemporaryDirectory(prefix='dub_sweep_test_')
        self.addCleanup(sandbox.cleanup)
        tempdir = patch('tempfile.gettempdir', return_value=sandbox.name)
        tempdir.start()
        self.addCleanup(tempdir.stop)

    def tearDown(self):
        for path in self._created:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path, ignore_errors=True)
        super().tearDown()

    def _make_temp_dir(self, age_seconds, owner_pid=None):
        """Create a backup-prefixed temp dir aged `age_seconds`, optionally
        with an owner marker for `owner_pid`."""
        path = tempfile.mkdtemp(prefix='odoo_backup_')
        self._created.append(path)
        if owner_pid is not None:
            marker = os.path.join(path, self.Job._TEMP_OWNER_MARKER)
            with open(marker, 'w') as fh:
                fh.write(str(owner_pid))
            past = time.time() - age_seconds
            os.utime(marker, (past, past))
        past = time.time() - age_seconds
        os.utime(path, (past, past))
        return path

    def _dead_pid(self):
        """Return the PID of a process that has already exited."""
        proc = subprocess.Popen(['true'])
        proc.wait()
        return proc.pid

    def test_recent_dir_is_kept(self):
        path = self._make_temp_dir(age_seconds=60)
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(path))

    def test_old_dir_with_live_owner_is_kept(self):
        """An in-progress backup (3h old, owner process alive) must survive
        the sweep — this is the bug where the hourly cron deleted the temp
        dir of long-running backups out from under the worker."""
        path = self._make_temp_dir(age_seconds=3 * 3600, owner_pid=os.getpid())
        self.Job._cleanup_stale_temp_files()
        self.assertTrue(os.path.isdir(path))

    def test_old_dir_with_dead_owner_is_removed(self):
        path = self._make_temp_dir(age_seconds=3 * 3600, owner_pid=self._dead_pid())
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_old_dir_without_marker_is_removed(self):
        """Dirs created by a pre-marker version of the module fall back to
        pure age-based cleanup."""
        path = self._make_temp_dir(age_seconds=3 * 3600)
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_hard_cap_removes_even_live_owner(self):
        """Past the hard cap the dir goes regardless of the owner, bounding
        leakage when a recycled PID matches an unrelated live process."""
        path = self._make_temp_dir(age_seconds=25 * 3600, owner_pid=os.getpid())
        self.Job._cleanup_stale_temp_files()
        self.assertFalse(os.path.exists(path))

    def test_marker_is_written_and_detected(self):
        path = tempfile.mkdtemp(prefix='odoo_backup_')
        self._created.append(path)
        self.Job._mark_temp_dir_owner(path)
        self.assertTrue(
            os.path.exists(os.path.join(path, self.Job._TEMP_OWNER_MARKER)))
        self.assertTrue(self.Job._temp_dir_owner_alive(path))
