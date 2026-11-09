# -*- coding: utf-8 -*-
# Copyright 2026 René Hechavarría
"""
Tests for the attempt limit of the backup queue.

A backup whose Odoo process stops mid-run (an Odoo reload after a cron time
limit, a memory limit, a restart) leaves no error behind. The queue records
every attempt before any heavy work, starts such a backup once more, and then
marks it as failed instead of starting it every minute forever. A backup that
fails with an error, such as a full disk, is never started again.
"""
import errno
import tempfile
from unittest.mock import MagicMock, patch

from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import config

from odoo.addons.database_ultimate_backup_lite.models.backup_utils import cron_time_limit


@tagged('post_install', '-at_install')
class TestJobAttempts(TransactionCase):

    def setUp(self):
        super().setUp()
        storage = tempfile.TemporaryDirectory(prefix='dub_attempts_')
        self.addCleanup(storage.cleanup)
        provider = self.env['backup.provider.local'].create({
            'name': 'Attempts Storage', 'backup_directory': storage.name, 'check_disk_space': False,
        })
        self.config = self.env['backup.config'].create({
            'name': 'Attempts Backup', 'local_provider_ids': [Command.set(provider.ids)],
        })
        self.Job = self.env['backup.job']
        self.events = []
        self.commit_progress = self._patch(type(self.env['ir.cron']), '_commit_progress',
                                           side_effect=self._record_commit)
        self.sweep = self._patch(type(self.Job), '_cleanup_stale_temp_files')
        self.notify = self._patch(type(self.config), '_send_notification')

    def _patch(self, target, name, **kwargs):
        patcher = patch.object(target, name, **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _record_commit(self, *args, **kwargs):
        self.events.extend(('commit', job.status, job.attempt_count) for job in self.jobs)
        return 0

    def _job(self, status='pending', attempts=0, started_minutes_ago=0):
        job = self.Job.create({
            'config_id': self.config.id, 'database_name': self.env.cr.dbname,
            'backup_format': 'zip', 'status': status, 'attempt_count': attempts,
        })
        # The takeover delay is measured with the database clock.
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE backup_job SET start_time = now() AT TIME ZONE 'UTC' - make_interval(mins => %s)
            WHERE id = %s
        """, [started_minutes_ago, job.id])
        job.invalidate_recordset(['start_time'])
        self.jobs = job
        return job

    def _fake_backup(self, job):
        self.events.append(('backup', job.status, job.attempt_count))
        job.write({'status': 'success', 'end_time': fields.Datetime.now()})
        return {'success': True, 'message': 'Backup completed successfully', 'backup_job': job}

    def _run_queue(self, process=None):
        if process is None:
            def process(job):
                return self._fake_backup(job)
        with patch.object(type(self.Job), '_process_backup', process):
            self.Job.run_pending_backups()

    def test_attempt_is_committed_before_the_backup_runs(self):
        """If the process dies during the backup, the attempt is already recorded."""
        job = self._job()
        self._run_queue()
        self.assertEqual(self.events, [
            ('commit', 'running', 1),
            ('backup', 'running', 1),
            ('commit', 'success', 1),
        ])
        self.assertIn('Attempt 1 of 2 started', job.log_entries)

    def test_interrupted_attempt_is_started_once_more(self):
        job = self._job(status='running', attempts=1, started_minutes_ago=60)
        self._run_queue()
        self.assertIn(('backup', 'running', 2), self.events)
        self.assertEqual(job.status, 'success')
        self.assertIn('Attempt 1 did not finish', job.log_entries)
        self.assertIn('Attempt 2 of 2 started', job.log_entries)

    def test_second_interrupted_attempt_fails_and_notifies(self):
        job = self._job(status='running', attempts=2, started_minutes_ago=60)
        backup = MagicMock()
        with patch.dict(config.options, {'limit_time_real_cron': -1, 'limit_time_real': 120}):
            self._run_queue(backup)
        backup.assert_not_called()
        self.assertEqual(job.status, 'error')
        self.assertEqual(job.attempt_count, 2)
        self.assertTrue(job.end_time)
        self.assertIn('stopped in the middle of this backup on each of its 2 attempts', job.error_message)
        self.assertIn('longer than 120 seconds (limit_time_real, applied because '
                      'limit_time_real_cron is -1)', job.error_message)
        self.assertIn('set limit_time_real_cron', job.error_message)
        self.notify.assert_called_once_with(job, 'failure')
        self.assertEqual(self.config.last_backup_status, 'error')
        self.sweep.assert_called_once()

    def test_running_attempt_with_recent_start_is_left_alone(self):
        """A runner holds the lock of its job, except for the instant between
        committing the attempt and locking it again: a recent start covers it."""
        job = self._job(status='running', attempts=1, started_minutes_ago=0)
        backup = MagicMock()
        self._run_queue(backup)
        backup.assert_not_called()
        self.assertEqual(job.status, 'running')
        self.assertEqual(job.attempt_count, 1)

    def test_backup_failing_with_full_disk_is_not_started_again(self):
        job = self._job()
        full = OSError(errno.ENOSPC, 'No space left on device')
        with patch.object(type(self.Job), '_create_backup_file', side_effect=full) as create:
            self.Job.run_pending_backups()
            self.Job.run_pending_backups()
        create.assert_called_once()
        self.assertEqual(job.status, 'error')
        self.assertEqual(job.attempt_count, 1)
        self.assertIn('No space left on device', job.error_message)
        self.notify.assert_called_once_with(job, 'failure')

    def test_cron_time_limit_follows_odoo_19(self):
        cases = [
            ({'workers': 0, 'limit_time_real_cron': -1, 'limit_time_real': 120}, 120),
            # Threaded Odoo 19 falls back to limit_time_real when the cron limit is 0.
            ({'workers': 0, 'limit_time_real_cron': 0, 'limit_time_real': 120}, 120),
            ({'workers': 0, 'limit_time_real_cron': 7200, 'limit_time_real': 120}, 7200),
            ({'workers': 2, 'limit_time_real_cron': -1, 'limit_time_real': 120}, 120),
            ({'workers': 2, 'limit_time_real_cron': 0, 'limit_time_real': 120}, 0),
            ({'workers': 2, 'limit_time_real_cron': 7200, 'limit_time_real': 120}, 7200),
        ]
        for options, expected in cases:
            with self.subTest(options=options), patch.dict(config.options, options):
                self.assertEqual(cron_time_limit()[0], expected)

    def test_message_without_time_limit_points_to_memory_and_restarts(self):
        job = self._job(status='running', attempts=2, started_minutes_ago=60)
        with patch.dict(config.options, {'workers': 2, 'limit_time_real_cron': 0}):
            self._run_queue(MagicMock())
        self.assertIn('No time limit applies to scheduled actions', job.error_message)
        self.assertIn('limit_memory_soft', job.error_message)
