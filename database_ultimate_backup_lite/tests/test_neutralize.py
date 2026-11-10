# -*- coding: utf-8 -*-
# Copyright 2026 René Hechavarría
"""
Tests for data/neutralize.sql: neutralized copies (odoo-bin neutralize, or a
restore or duplication with "Neutralize") drop the SFTP password.
"""
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNeutralization(TransactionCase):

    def _create_sftp(self):
        provider = self.env['backup.provider.sftp'].create({
            'name': 'Production SFTP',
            'hostname': 'backup.example.com',
            'username': 'odoo',
            'password': 'secret',
            'remote_directory': '/backups',
        })
        self.env.flush_all()
        return provider

    def _neutralize(self):
        for query in get_neutralization_queries(['database_ultimate_backup_lite']):
            self.env.cr.execute(query)

    def test_neutralization_drops_the_sftp_password(self):
        provider = self._create_sftp()
        self._neutralize()
        self.env.invalidate_all()
        provider = provider.sudo()
        self.assertFalse(provider.password)
        self.assertEqual(provider.hostname, 'backup.example.com', 'only the secret is dropped')

    def test_neutralization_runs_on_a_schema_without_the_column(self):
        """Odoo neutralizes a restored or duplicated database before any upgrade, so
        a secret added in a later version may not have its column yet."""
        self._create_sftp()
        cr = self.env.cr
        with cr.savepoint(flush=False) as savepoint:
            cr.execute('ALTER TABLE backup_provider_sftp DROP COLUMN password')
            self._neutralize()
            savepoint.rollback()
        self.env.invalidate_all()
