import io
import json
from pathlib import Path
import runpy
import struct
import tempfile
from unittest.mock import Mock, patch
import zipfile

import odoo.tools
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..models import backup_job as job_module


@tagged('post_install', '-at_install')
class TestBackup(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reader = cls.env['res.users'].create({
            'name': 'Backup reader', 'login': 'backup_regression_reader',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('database_ultimate_backup_lite.group_backup_user').id,
            ])],
        })
        cls.admin = cls.env['res.users'].create({
            'name': 'Backup administrator', 'login': 'backup_regression_admin',
            'group_ids': [Command.set([
                cls.env.ref('base.group_user').id,
                cls.env.ref('database_ultimate_backup_lite.group_backup_admin').id,
            ])],
        })

    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory(prefix='lite19_test_')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.local = self.env['backup.provider.local'].create({
            'name': 'Local regression', 'backup_directory': str(self.root / 'backups'),
            'check_disk_space': False,
        })
        self.sftp = self.env['backup.provider.sftp'].create({
            'name': 'SFTP regression', 'hostname': 'example.invalid',
            'username': 'backup', 'password': 'test-only-password',
        })
        self.config = self.env['backup.config'].create({
            'name': 'Regression backup', 'local_provider_ids': [Command.set(self.local.ids)],
            'notify_failure': False,
        })
        self.job = self.env['backup.job'].create({
            'config_id': self.config.id, 'database_name': self.env.cr.dbname,
            'backup_format': 'zip', 'status': 'error',
        })
        self.patch(type(self.job), '_cleanup_stale_temp_files', lambda *a, **kw: None)

    def _dump_directory(self):
        dump = self.root / 'dump'
        dump.mkdir(exist_ok=True)
        (dump / 'dump.sql').write_text('SELECT 1;', encoding='utf-8')
        (dump / 'manifest.json').write_text(json.dumps({'db_name': self.env.cr.dbname}))
        return dump

    def _backup_file(self, directory):
        path = Path(directory) / 'backup.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('dump.sql', 'SELECT 1;')
            archive.writestr('manifest.json', json.dumps({'db_name': self.env.cr.dbname}))
        return str(path)

    def test_zip_filestore_selection_and_symlink_boundary(self):
        dump = self._dump_directory()
        filestore = self.root / 'filestore'
        filestore.mkdir()
        (filestore / 'attachment').write_bytes(b'attachment')
        outside = self.root / 'outside'
        outside.write_bytes(b'not an attachment')
        (filestore / 'outside_link').symlink_to(outside)
        (filestore / 'inside_link').symlink_to(filestore / 'attachment')
        (filestore / 'missing_link').symlink_to(self.root / 'missing')
        for include in (True, False):
            with self.subTest(include=include):
                output = io.BytesIO()
                with patch.object(odoo.tools.config, 'filestore', return_value=str(filestore)) as lookup:
                    self.job._write_backup_zip(output, str(dump), self.env.cr.dbname, include)
                    if not include:
                        lookup.assert_not_called()
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(archive.namelist()[:2], ['dump.sql', 'manifest.json'])
                    expected = {'dump.sql', 'manifest.json'}
                    if include:
                        expected.update({'filestore/attachment', 'filestore/inside_link'})
                    self.assertEqual(set(archive.namelist()), expected)
                    self.assertIsNone(archive.testzip())

    def test_filestore_choice_is_copied_to_job(self):
        self.assertTrue(self.config.include_filestore)
        self.config.include_filestore = False
        def process(job):
            job.status = 'success'
            return {'success': True, 'backup_job': job}
        with patch.object(type(self.job), '_process_backup', process):
            job = self.config.with_context(manual_execution=False).create_backup()
        self.assertFalse(job.include_filestore)
        self.config.include_filestore = True
        self.assertFalse(job.include_filestore)

    def test_custom_dump_never_claims_filestore(self):
        job = self.env['backup.job'].create({
            'config_id': self.config.id, 'database_name': self.env.cr.dbname,
            'backup_format': 'dump', 'include_filestore': True,
        })
        self.assertFalse(job.include_filestore)

    def test_valid_zip_without_filestore_passes_verification(self):
        path = self._backup_file(self.root)
        self.job._verify_backup_integrity(path)
        self.assertEqual(self.job.verification_status, 'verified')

    def test_corrupt_zip_member_is_rejected(self):
        path = Path(self._backup_file(self.root))
        data = bytearray(path.read_bytes())
        name_size, extra_size = struct.unpack_from('<HH', data, 26)
        data[30 + name_size + extra_size] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(UserError, 'integrity check failed for: dump.sql'):
            self.job._verify_backup_integrity(str(path))
        self.assertEqual(self.job.verification_status, 'failed')

    def test_empty_file_never_reaches_provider(self):
        self.config.verify_backups = False
        def empty_file(job, directory):
            path = Path(directory) / 'empty.dump'
            path.touch()
            return str(path)
        with patch.object(type(self.job), '_create_backup_file', empty_file), \
             patch.object(type(self.job), '_upload_to_providers') as upload:
            result = self.job._process_backup()
        self.assertFalse(result['success'])
        self.assertEqual(self.job.status, 'error')
        self.assertIn('empty', self.job.error_message)
        upload.assert_not_called()

    def test_custom_dump_checks_process_exit_after_partial_output(self):
        process = Mock(stdout=io.BytesIO(b'PGDMPpartial'))
        process.wait.return_value = 1
        def start(*args, **kwargs):
            kwargs['stderr'].write(b'permission denied reading database')
            return process
        with patch.object(job_module, 'exp_db_exist', return_value=True), \
             patch.object(job_module, 'find_pg_tool', return_value='pg_dump'), \
             patch.object(job_module.subprocess, 'Popen', side_effect=start):
            with self.assertRaisesRegex(UserError, 'pg_dump failed.*permission denied'):
                self.job._dump_db(self.env.cr.dbname, io.BytesIO(), 'dump')
        process.wait.assert_called_once()
        self.assertTrue(process.stdout.closed)

    def test_custom_dump_success_and_stream_failure_cleanup(self):
        for stream_fails in (False, True):
            with self.subTest(stream_fails=stream_fails):
                process = Mock(stdout=io.BytesIO(b'PGDMPdata'))
                process.wait.return_value = 0
                process.poll.return_value = None
                output = Mock() if stream_fails else io.BytesIO()
                if stream_fails:
                    output.write.side_effect = OSError('disk full')
                with patch.object(job_module, 'exp_db_exist', return_value=True), \
                     patch.object(job_module, 'find_pg_tool', return_value='pg_dump'), \
                     patch.object(job_module.subprocess, 'Popen', return_value=process):
                    if stream_fails:
                        with self.assertRaisesRegex(OSError, 'disk full'):
                            self.job._dump_db(self.env.cr.dbname, output, 'dump')
                        process.kill.assert_called_once()
                    else:
                        self.job._dump_db(self.env.cr.dbname, output, 'dump')
                        self.assertEqual(output.getvalue(), b'PGDMPdata')
                process.wait.assert_called_once()
                self.assertTrue(process.stdout.closed)

    def test_zip_pg_dump_failure_reports_stderr_and_cleans_temp(self):
        result = Mock(returncode=1, stderr=b'could not read table')
        dump_dir = self.root / 'dump_temp'
        dump_dir.mkdir()
        with patch.object(job_module, 'exp_db_exist', return_value=True), \
             patch.object(job_module.tempfile, 'mkdtemp', return_value=str(dump_dir)), \
             patch.object(job_module, 'find_pg_tool', return_value='pg_dump'), \
             patch.object(job_module.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(UserError, 'pg_dump failed.*could not read table'):
                self.job._dump_db(self.env.cr.dbname, io.BytesIO())
        self.assertFalse(dump_dir.exists())

    def test_dump_rejects_invalid_format_or_missing_database(self):
        with self.assertRaisesRegex(ValueError, 'unknown backup_format'):
            self.job._dump_db(self.env.cr.dbname, io.BytesIO(), 'invalid')
        with patch.object(job_module, 'exp_db_exist', return_value=False), \
             patch.object(job_module.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, "doesn't exist"):
                self.job._dump_db('missing', io.BytesIO(), 'dump')
            process.assert_not_called()

    def test_backup_admin_can_dump_with_list_db_disabled(self):
        job = self.job.with_user(self.admin)
        job.include_filestore = False
        with patch.dict(odoo.tools.config.options, {'list_db': False}), \
             patch.object(type(job), '_is_odoo_sh', return_value=False), \
             patch.object(type(job), '_dump_db') as dump:
            stream = io.BytesIO()
            job._create_database_dump(stream)
        dump.assert_called_once_with(self.env.cr.dbname, stream, 'zip', with_filestore=False)

    def test_reader_cannot_invoke_storage_operations(self):
        methods = {
            'test_connection': (), 'test_connection_action': (),
            'upload_backup': ('unused-source', 'unused.dump'),
            'download_backup': ('unused.dump', 'unused-target'),
            'delete_backup': ('unused.dump',), 'list_backups': (), 'get_storage_info': (),
        }
        for provider in (self.local, self.sftp):
            for name, args in methods.items():
                with self.subTest(provider=provider._name, method=name), self.assertRaises(AccessError):
                    getattr(provider.with_user(self.reader), name)(*args)
        with self.assertRaises(AccessError):
            self.sftp.with_user(self.reader).action_reset_host_key()

    def test_dump_authorization_does_not_trust_execution_flags(self):
        self.job.is_manual = False
        with patch.object(type(self.job), '_dump_db') as dump:
            with self.assertRaises(AccessError):
                self.job.with_user(self.reader).with_context(manual_execution=False)._create_database_dump(io.BytesIO())
        dump.assert_not_called()

    def test_reader_can_read_history_but_not_password_or_actions(self):
        self.assertTrue(self.job.with_user(self.reader).read(['status']))
        self.assertTrue(self.config.with_user(self.reader).read(['name', 'include_filestore']))
        with self.assertRaises(AccessError):
            self.sftp.with_user(self.reader).read(['password'])
        self.assertEqual(self.sftp.with_user(self.admin).password, 'test-only-password')
        for method in ('create_backup', 'test_providers', 'test_retention_policy', 'cleanup_old_backups'):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(self.config.with_user(self.reader), method)()

    def test_admin_local_provider_and_display_name(self):
        result = self.local.with_user(self.admin).test_connection()
        self.assertTrue(result['success'])
        self.assertEqual(self.local.display_name, 'Local regression (Local Storage)')

    def test_partial_upload_stays_warning_in_config_and_notification(self):
        self.config.sftp_provider_ids = [Command.set(self.sftp.ids)]
        self.config.notify_failure = True
        def create_file(job, directory):
            return self._backup_file(directory)
        with patch.object(type(self.job), '_create_backup_file', create_file), \
             patch.object(type(self.local), 'upload_backup', return_value={'success': True}), \
             patch.object(type(self.sftp), 'upload_backup', return_value={'success': False, 'message': 'offline'}), \
             patch.object(type(self.config), '_send_notification') as notify:
            action = self.config.create_backup()
            with patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=0):
                self.env['backup.job'].run_pending_backups()
        job = self.env['backup.job'].browse(action['res_id'])
        self.assertEqual(job.status, 'warning')
        self.assertEqual(self.config.last_backup_status, 'warning')
        self.assertEqual(action['type'], 'ir.actions.act_window')
        notify.assert_called_once_with(job, 'warning')

    def test_scheduler_passes_filestore_selection(self):
        self.config.include_filestore = False
        self.env['backup.config'].search([('id', '!=', self.config.id)]).active = False
        def process(job):
            self.assertFalse(job.include_filestore)
            job.status = 'success'
            return {'success': True, 'backup_job': job}
        cron = self.env.ref('database_ultimate_backup_lite.backup_cron')
        with patch.object(type(self.job), '_process_backup', process), \
             patch.object(type(self.config), 'cleanup_old_backups') as cleanup:
            self.env['backup.config'].with_user(cron.user_id).run_scheduled_backups()
            queued = self.config.backup_job_ids.filtered(lambda job: job.status == 'pending')
            self.assertEqual(len(queued), 1)
            self.assertFalse(queued.include_filestore)
            cleanup.assert_not_called()
            with patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=0):
                self.env['backup.job'].run_pending_backups()
        created = self.config.backup_job_ids.sorted('id')[-1]
        self.assertFalse(created.is_manual)
        self.assertFalse(created.include_filestore)
        self.assertEqual(self.config.last_backup_status, 'success')
        cleanup.assert_called_once()

    def test_upgrade_initializes_legacy_filestore_flags(self):
        custom = self.job.copy({'backup_format': 'dump'})
        self.env.flush_all()
        self.env.cr.execute('UPDATE backup_config SET include_filestore = FALSE WHERE id = %s', [self.config.id])
        self.env.cr.execute('UPDATE backup_job SET include_filestore = TRUE WHERE id = %s', [custom.id])
        migration = Path(__file__).parents[1] / 'migrations/19.0.1.5.0/post-migrate.py'
        runpy.run_path(str(migration))['migrate'](self.env.cr, '19.0.1.4.2')
        self.env.invalidate_all()
        self.assertTrue(self.config.include_filestore)
        self.assertTrue(self.job.include_filestore)
        self.assertFalse(custom.include_filestore)
