"""Regression coverage for backup authorization, integrity, retention and execution."""
import asyncio
import datetime
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.service.model import get_public_method
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestBackupHardening(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = new_test_user(cls.env, login='backup_viewer_test',
                                   groups='base.group_user,database_ultimate_backup_lite.group_backup_user')
        cls.regular = new_test_user(cls.env, login='backup_regular_test', groups='base.group_user')
        cls.backup_admin = new_test_user(
            cls.env, login='backup_admin_test',
            groups='base.group_user,database_ultimate_backup_lite.group_backup_admin',
        )

    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory(prefix='dub_hardening_')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = self.root / 'storage'
        self.storage.mkdir()
        self.provider = self.env['backup.provider.local'].create({
            'name': 'Test Storage', 'backup_directory': str(self.storage), 'check_disk_space': False,
        })
        self.config = self.env['backup.config'].create({
            'name': 'Test Backup', 'local_provider_ids': [Command.set(self.provider.ids)],
        })
        self.job = self.env['backup.job'].create({
            'config_id': self.config.id, 'database_name': self.env.cr.dbname,
            'backup_format': 'zip', 'status': 'error',
        })

    def _archive(self, *, sql=b'SELECT 1;', corrupt=False):
        archive = self.root / 'backup.zip'
        attachment = b'unique-attachment-content-for-crc-test'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as zf:
            zf.writestr('dump.sql', sql)
            zf.writestr('manifest.json', json.dumps({'db_name': self.env.cr.dbname}))
            zf.writestr('filestore/aa/file', attachment)
        if corrupt:
            data = bytearray(archive.read_bytes())
            data[data.index(attachment)] ^= 1
            archive.write_bytes(data)
        return str(archive)

    def _record_upload(self, config, filename, location, *, metadata_key='file_path'):
        return self.env['backup.job'].create({
            'config_id': config.id, 'database_name': config.database_name,
            'backup_format': 'zip', 'status': 'success', 'backup_filename': filename,
            'provider_results': json.dumps({f'{self.provider._name}:{self.provider.id}': {
                'success': True, 'metadata': {metadata_key: str(location)},
            }}),
        })

    def test_viewer_cannot_execute_external_operations(self):
        for method, args in (('delete_backup', ('missing.zip',)),
                             ('upload_backup', ('/unused', 'test.zip')),
                             ('download_backup', ('test.zip', '/unused')),
                             ('test_connection_action', ())):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(self.provider.with_user(self.viewer), method)(*args)
        for method in ('create_backup', 'cleanup_old_backups', 'test_providers', 'test_retention_policy'):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(self.config.with_user(self.viewer), method)()

    def test_local_paths_cannot_escape_storage(self):
        outside = self.root / 'outside.zip'
        outside.write_bytes(b'protected')
        for filename in ('../outside.zip', str(outside), '..\\outside.zip'):
            with self.subTest(filename=filename), self.assertRaises(ValidationError):
                self.provider.delete_backup(filename)
        (self.storage / 'linked.zip').symlink_to(outside)
        self.assertFalse(self.provider.delete_backup('linked.zip')['success'])
        self.assertEqual(outside.read_bytes(), b'protected')

    def test_upload_rejects_directory_symlink_escape(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (self.storage / 'linked').symlink_to(outside, target_is_directory=True)
        source = self.root / 'source'
        source.write_bytes(b'data')
        with patch.object(type(self.provider), '_get_target_directory', return_value=str(self.storage / 'linked')):
            self.assertFalse(self.provider.upload_backup(str(source), 'test.zip')['success'])
        self.assertFalse(list(outside.iterdir()))

    def test_valid_zip_passes_and_corrupted_attachment_fails(self):
        self.job._verify_zip_backup(self._archive())
        with self.assertRaises(UserError):
            self.job._verify_zip_backup(self._archive(corrupt=True))

    def test_empty_sql_and_truncated_dump_are_rejected(self):
        with self.assertRaises(UserError):
            self.job._verify_zip_backup(self._archive(sql=b''))
        truncated = self.root / 'truncated.dump'
        truncated.write_bytes(b'PGDMP')
        with self.assertRaises(UserError):
            self.job._verify_dump_backup(str(truncated))

    def test_local_verification_fails_closed(self):
        self.assertFalse(self.provider._verify_backup_integrity(
            str(self.root / 'missing-1'), str(self.root / 'missing-2')))

    def test_local_upload_is_private_and_honors_directory_limit(self):
        source = self.root / 'source'
        source.write_bytes(b'data' * 1000)
        result = self.provider.upload_backup(str(source), 'test.zip')
        self.assertTrue(result['success'], result['message'])
        target = self.storage / 'test.zip'
        self.assertEqual(source.read_bytes(), target.read_bytes())
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o600)
        self.provider.max_directory_size_gb = 0.000001
        self.assertFalse(self.provider.upload_backup(str(source), 'too-big.zip')['success'])
        self.assertFalse((self.storage / 'too-big.zip').exists())

    def test_retention_normalizes_dates_and_keeps_latest(self):
        now = fields.Datetime.now()
        old = now - datetime.timedelta(days=30)
        self.config.write({'retention_policy': 'days', 'retention_days': 7})
        backups = [
            {'filename': 'new.zip', 'created_date': now.replace(tzinfo=datetime.timezone.utc)},
            {'filename': 'old.zip', 'created_date': old.isoformat() + 'Z'},
            {'filename': 'unknown.zip'},
        ]
        self.assertEqual([b['filename'] for b in self.config._get_backups_to_delete(backups)], ['old.zip'])
        self.assertEqual(self.config._get_backups_to_delete([backups[1]]), [])

    def test_retention_never_deletes_other_config_or_untracked_files(self):
        other = self.config.copy({'name': 'Other policy'})
        files = {name: self.storage / name for name in ('old.zip', 'new.zip', 'other.zip', 'untracked.zip')}
        for filename, location in files.items():
            location.write_bytes(b'backup')
            if filename != 'untracked.zip':
                self._record_upload(other if filename == 'other.zip' else self.config, filename, location)
        now = fields.Datetime.now()
        listed = [{'filename': filename, 'full_path': str(location),
                   'created_date': now - datetime.timedelta(days=10 if filename == 'old.zip' else 1)}
                  for filename, location in files.items()]
        self.config.retention_count = 1
        with patch.object(type(self.provider), 'list_backups', return_value=listed):
            self.config.cleanup_old_backups()
        self.assertFalse(files['old.zip'].exists())
        self.assertTrue(all(files[name].exists() for name in ('new.zip', 'other.zip', 'untracked.zip')))

    def test_ambiguous_legacy_locations_are_preserved(self):
        location = self.storage / 'shared.zip'
        self._record_upload(self.config, location.name, location)
        other = self.config.copy({'name': 'Other policy'})
        self._record_upload(other, location.name, location)
        with patch.object(type(self.provider), 'list_backups', return_value=[
            {'filename': location.name, 'full_path': str(location), 'created_date': fields.Datetime.now()},
        ]):
            self.assertFalse(self.config._get_owned_backups(self.provider))

    def test_retention_recognizes_legacy_local_directory_alias(self):
        alias = self.root / 'storage-alias'
        alias.symlink_to(self.storage, target_is_directory=True)
        self.provider.backup_directory = str(alias)
        legacy_path = alias / 'legacy.zip'
        legacy_path.write_bytes(b'legacy archive')
        self._record_upload(self.config, legacy_path.name, legacy_path)
        owned = self.config._get_owned_backups(self.provider)
        self.assertEqual(len(owned), 1)
        self.assertEqual(owned[0]['full_path'], str((self.storage / 'legacy.zip').resolve()))

    def test_legacy_collision_with_another_provider_record_is_preserved(self):
        location = self.storage / 'legacy.zip'
        self._record_upload(self.config, location.name, location)
        other_provider = self.provider.copy({'name': 'Same directory, different record'})
        other_config = self.config.copy({
            'name': 'Other policy', 'local_provider_ids': [Command.set(other_provider.ids)],
        })
        other_job = self._record_upload(other_config, location.name, location)
        other_job.provider_results = json.dumps({f'{other_provider._name}:{other_provider.id}': {
            'success': True, 'metadata': {'file_path': str(location)},
        }})
        with patch.object(type(self.provider), 'list_backups', return_value=[{
            'filename': location.name, 'full_path': str(location), 'created_date': fields.Datetime.now(),
        }]):
            self.assertFalse(self.config._get_owned_backups(self.provider))

    def test_retention_policy_switch_validates_existing_limits(self):
        self.config.write({'retention_policy': 'custom', 'retention_count': 0})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.config.retention_policy = 'count'

    def test_manual_backup_queues_without_running_dump(self):
        with patch.object(type(self.job), '_process_backup', side_effect=AssertionError('must be queued')):
            action = self.config.create_backup()
        queued = self.env['backup.job'].browse(action['res_id'])
        self.assertEqual(queued.status, 'pending')
        with self.assertRaises(UserError):
            self.config.create_backup()

    def test_backup_administrator_can_queue_without_system_rights(self):
        self.assertFalse(self.backup_admin.has_group('base.group_system'))
        action = self.config.with_user(self.backup_admin).create_backup()
        queued = self.env['backup.job'].browse(action['res_id'])
        self.assertEqual(queued.status, 'pending')

    def test_database_error_in_job_does_not_poison_the_queue(self):
        action = self.config.create_backup()
        queued = self.env['backup.job'].browse(action['res_id'])

        def fail_with_database_error(job):
            job.env.cr.execute('SELECT 1 / 0')

        with patch.object(type(queued), '_process_backup', fail_with_database_error), \
                patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=0):
            self.env['backup.job'].run_pending_backups()
        self.assertEqual(queued.status, 'error')
        self.assertIn('division by zero', queued.error_message)
        self.assertEqual(self.config.last_backup_status, 'error')

    def test_notification_database_error_preserves_finished_backup(self):
        self.job.status = 'success'

        def fail_notification(config, job, event):
            config.env.cr.execute('SELECT 1 / 0')

        with patch.object(type(self.config), '_send_notification', fail_notification), \
                patch.object(type(self.config), 'cleanup_old_backups') as cleanup:
            self.config._finish_backup(self.job, {
                'success': True, 'backup_job': self.job, 'message': 'Backup completed',
            })
        self.env.flush_all()
        self.assertEqual(self.job.status, 'success')
        self.assertEqual(self.config.last_backup_status, 'success')
        cleanup.assert_called_once()

    def test_retention_database_error_preserves_finished_backup(self):
        self.job.status = 'success'

        def fail_cleanup(config):
            config.env.cr.execute('SELECT 1 / 0')

        with patch.object(type(self.config), 'cleanup_old_backups', fail_cleanup):
            self.config._finish_backup(self.job, {
                'success': True, 'backup_job': self.job, 'message': 'Backup completed',
            })
        self.env.flush_all()
        self.assertEqual(self.job.status, 'success')
        self.assertEqual(self.config.last_backup_status, 'success')

    def test_queue_records_early_failures_and_updates_configuration(self):
        action = self.config.create_backup()
        queued = self.env['backup.job'].browse(action['res_id'])
        with patch.object(type(queued), '_create_backup_file', side_effect=UserError('Source unavailable')), \
                patch.object(type(queued), '_cleanup_stale_temp_files'), \
                patch.object(type(self.env['ir.cron']), '_commit_progress', return_value=0):
            self.env['backup.job'].run_pending_backups()
        self.assertEqual(queued.status, 'error')
        self.assertIn('Source unavailable', queued.error_message)
        self.assertTrue(queued.end_time)
        self.assertEqual(self.config.last_backup_status, 'error')

    def test_partial_uploads_produce_warning_and_archive_checksum(self):
        other = self.provider.copy({'name': 'Unavailable destination'})
        self.config.local_provider_ids = [Command.link(other.id)]
        archive = self._archive()
        with patch.object(type(self.job), '_create_backup_file', return_value=archive), \
                patch.object(type(self.job), '_cleanup_stale_temp_files'), \
                patch.object(type(self.job), '_upload_to_providers', return_value={
                    'first': {'success': True}, 'second': {'success': False},
                }):
            result = self.job._process_backup()
        self.assertTrue(result['success'])
        self.assertEqual(self.job.status, 'warning')
        self.assertEqual(self.job.backup_sha256, hashlib.sha256(Path(archive).read_bytes()).hexdigest())
        self.assertEqual(self.job.verification_status, 'verified')

    def test_provider_results_do_not_collide_when_names_match(self):
        second_storage = self.root / 'second'
        second_storage.mkdir()
        other = self.provider.copy({'backup_directory': str(second_storage)})
        other.name = self.provider.name
        self.job.backup_filename = 'test.zip'
        archive = self._archive()
        results = self.job._upload_to_providers_sequential(archive, self.provider | other)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result['success'] for result in results.values()))

    def test_warning_email_uses_v19_parameters_and_warning_subject(self):
        self.env['ir.mail_server'].create({
            'name': 'Test SMTP', 'smtp_host': 'example.invalid', 'smtp_user': 'backup@example.invalid',
        })
        self.env['ir.config_parameter'].set_param('mail.catchall.domain', 'example.invalid')
        self.config.write({'notify_failure': True, 'notification_emails': 'admin@example.invalid'})
        self.job.status = 'warning'
        with patch.object(type(self.env['ir.mail_server']), 'send_email') as send:
            self.config._send_notification(self.job, 'success')
        send.assert_called_once()
        message = send.call_args.args[0]
        self.assertIn('Completed with Warnings', str(message['Subject']))
        self.assertEqual(str(message['From']), 'backup@example.invalid')

    def test_retry_preserves_failed_job_history(self):
        self.job.write({'error_message': 'Original failure', 'log_entries': 'Original evidence'})
        action = self.job.retry_backup()
        self.assertNotEqual(action['res_id'], self.job.id)
        self.assertEqual(self.job.error_message, 'Original failure')
        self.assertEqual(self.job.log_entries, 'Original evidence')

    def test_new_filenames_do_not_overwrite_previous_runs(self):
        self.config.backup_name_template = 'fixed.zip'
        self.assertNotEqual(self.job._generate_backup_filename(), self.job._generate_backup_filename())

    def _sftp(self):
        return self.env['backup.provider.sftp'].create({
            'name': 'SFTP fixture', 'hostname': 'example.invalid', 'username': 'odoo',
            'password': 'test-secret', 'remote_directory': '/backups',
        })

    def test_transfer_and_scheduler_methods_are_not_rpc_endpoints(self):
        for model in ('backup.provider.local', 'backup.provider.sftp'):
            for method in ('upload_backup', 'download_backup', 'delete_backup',
                           'list_backups', 'get_storage_info', 'test_connection'):
                with self.subTest(model=model, method=method), self.assertRaises(AccessError):
                    get_public_method(self.env[model], method)
        for model, method in (('backup.config', 'run_scheduled_backups'),
                              ('backup.job', 'run_pending_backups')):
            with self.subTest(model=model), self.assertRaises(AccessError):
                get_public_method(self.env[model], method)

    def test_sftp_credentials_are_protected_and_admin_can_duplicate(self):
        provider = self._sftp()
        self.assertTrue(provider.with_user(self.viewer).read(['name']))
        with self.assertRaises(AccessError):
            provider.with_user(self.viewer).read(['password'])
        with self.assertRaises(AccessError):
            provider.with_user(self.viewer).copy_data()
        duplicate = provider.with_user(self.backup_admin).copy()
        self.assertEqual(duplicate.password, 'test-secret')
        self.assertFalse(duplicate.server_host_key)

    def test_sftp_viewer_cannot_transfer_or_reset_host_key(self):
        provider = self._sftp().with_user(self.viewer)
        for method, args in (('upload_backup', ('/unused', 'test.zip')),
                             ('download_backup', ('test.zip', '/unused')),
                             ('delete_backup', ('test.zip',)), ('action_reset_host_key', ())):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(provider, method)(*args)

    def test_sftp_rejects_paths_before_connecting(self):
        provider = self._sftp()
        for filename in ('../other.zip', '/etc/passwd', 'folder/file.zip', 'folder\\file.zip'):
            for method, args in (('upload_backup', ('/unused', filename)),
                                 ('download_backup', (filename, '/unused')),
                                 ('delete_backup', (filename,))):
                with self.subTest(method=method, filename=filename), self.assertRaises(ValidationError):
                    getattr(provider, method)(*args)

    def test_sftp_transfer_timeout_cancels_upload_and_download(self):
        provider = self._sftp()
        provider.transfer_timeout = 1
        for method, args in (('upload_backup', ('/unused', 'test.zip')),
                             ('download_backup', ('test.zip', '/unused'))):
            cancelled = []

            async def blocked_transfer(record, *arguments):
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.append(True)

            with self.subTest(method=method), patch.object(type(provider), '_async_' + method, blocked_transfer):
                result = getattr(provider, method)(*args)
                self.assertFalse(result['success'])
                self.assertIn('timeout', result['message'])
                self.assertEqual(cancelled, [True])

    def test_zero_sftp_timeout_allows_transfer(self):
        provider = self._sftp()
        provider.transfer_timeout = 0
        with patch.object(type(provider), '_async_upload_backup', new_callable=AsyncMock) as transfer:
            transfer.return_value = {'success': True}
            self.assertTrue(provider.upload_backup('/unused', 'test.zip')['success'])
            transfer.assert_awaited_once()

    def test_inactive_destinations_are_not_used(self):
        other = self.provider.copy({'name': 'Inactive destination', 'active': False})
        self.config.local_provider_ids = [Command.link(other.id)]
        self.assertEqual(self.config.all_providers, [self.provider])
        self.provider.active = False
        with self.assertRaises(UserError):
            self.config.create_backup()

    def test_warning_status_survives_statistics(self):
        self.job.status = 'warning'
        self.config._update_backup_statistics({'success': True, 'backup_job': self.job})
        self.assertEqual(self.config.last_backup_status, 'warning')

    def test_local_connection_test_preserves_existing_write_test_file(self):
        sentinel = self.storage / '.write_test'
        sentinel.write_text('Existing user data')
        self.assertTrue(self.provider.test_connection()['success'])
        self.assertEqual(sentinel.read_text(), 'Existing user data')

    def test_local_upload_failure_preserves_existing_backup(self):
        existing = self.storage / 'existing.zip'
        existing.write_bytes(b'Original backup')
        archive = self._archive()
        with patch.object(type(self.provider), '_verify_backup_integrity', return_value=False):
            result = self.provider.upload_backup(archive, existing.name)
        self.assertFalse(result['success'])
        self.assertEqual(existing.read_bytes(), b'Original backup')
        self.assertFalse(list(self.storage.glob('.upload-*')))

    def test_generated_file_has_private_permissions_for_sftp(self):
        self.job.backup_filename = 'private.dump'
        with patch.object(type(self.job), '_create_database_dump', side_effect=lambda stream: stream.write(b'fixture')):
            path = self.job._create_backup_file(str(self.root))
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_lite_still_reports_odoo_sh_as_unsupported(self):
        with patch.object(type(self.job), '_is_odoo_sh', return_value=True), \
                patch.object(type(self.job), '_dump_db') as dump:
            with self.assertRaisesRegex(UserError, 'Lite cannot create backups on Odoo.sh'):
                self.job._create_database_dump(None)
            dump.assert_not_called()
