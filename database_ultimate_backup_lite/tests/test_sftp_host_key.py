# -*- coding: utf-8 -*-
# Copyright 2026 René Hechavarría
"""
Tests for SFTP host key pinning (trust on first use).

These tests never open a network connection: they exercise the pure
logic around `_get_connection_options`, `_pin_server_host_key`,
`_describe_connection_error` and `action_reset_host_key` using a fake
connection object, plus asyncssh's own key/known_hosts primitives.
"""
from unittest.mock import MagicMock

from odoo.tests.common import TransactionCase, tagged

try:
    import asyncssh
except ImportError:
    asyncssh = None


@tagged('post_install', '-at_install')
class TestSftpHostKeyPinning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['backup.provider.sftp'].create({
            'name': 'Test SFTP',
            'hostname': 'backup.example.com',
            'port': 2222,
            'username': 'odoo',
            'password': 'secret',
            'remote_directory': '/backups',
        })

    def _fake_conn_with_key(self, key):
        conn = MagicMock()
        conn.get_server_host_key.return_value = key
        return conn

    def test_first_connection_uses_tofu(self):
        """Without a pinned key, known_hosts must be None (TOFU)."""
        options = self.provider._get_connection_options()
        self.assertIsNone(options['known_hosts'])
        self.assertEqual(options['password'], 'secret')

    def test_pin_and_verify_round_trip(self):
        """The pinned key must produce a known_hosts object that matches
        the same key and rejects a different one."""
        if not asyncssh:
            self.skipTest("asyncssh not installed")

        key = asyncssh.generate_private_key('ssh-ed25519')
        fingerprint = self.provider._pin_server_host_key(
            self._fake_conn_with_key(key))

        self.assertTrue(fingerprint.startswith('SHA256:'))
        self.assertEqual(self.provider.host_key_fingerprint, fingerprint)
        self.assertIn('ssh-ed25519', self.provider.server_host_key)

        options = self.provider._get_connection_options()
        known_hosts = options['known_hosts']
        self.assertIsNotNone(known_hosts)

        # Non-22 port must be matched with the bracketed pattern
        matched = asyncssh.match_known_hosts(
            known_hosts, 'backup.example.com', None, 2222)[0]
        self.assertIn(key.convert_to_public(), matched)

        other_key = asyncssh.generate_private_key('ssh-ed25519')
        self.assertNotIn(other_key.convert_to_public(), matched)

    def test_pin_only_happens_once(self):
        """A second connection must not overwrite the pinned key."""
        if not asyncssh:
            self.skipTest("asyncssh not installed")

        key1 = asyncssh.generate_private_key('ssh-ed25519')
        key2 = asyncssh.generate_private_key('ssh-ed25519')

        first = self.provider._pin_server_host_key(self._fake_conn_with_key(key1))
        second = self.provider._pin_server_host_key(self._fake_conn_with_key(key2))

        self.assertTrue(first)
        self.assertIsNone(second)
        self.assertEqual(
            self.provider.server_host_key,
            key1.export_public_key().decode().strip(),
        )

    def test_no_pin_when_verification_disabled(self):
        if not asyncssh:
            self.skipTest("asyncssh not installed")

        self.provider.verify_host_key = False
        key = asyncssh.generate_private_key('ssh-ed25519')
        result = self.provider._pin_server_host_key(self._fake_conn_with_key(key))

        self.assertIsNone(result)
        self.assertFalse(self.provider.server_host_key)
        self.assertIsNone(self.provider._get_connection_options()['known_hosts'])

    def test_host_key_mismatch_error_message(self):
        """A host-key failure must produce the actionable security warning."""
        if not asyncssh:
            self.skipTest("asyncssh not installed")

        key = asyncssh.generate_private_key('ssh-ed25519')
        self.provider._pin_server_host_key(self._fake_conn_with_key(key))

        error = asyncssh.HostKeyNotVerifiable('Host key is not trusted')
        message = self.provider._describe_connection_error(error)

        self.assertIn('SECURITY WARNING', message)
        self.assertIn('backup.example.com', message)
        self.assertIn(self.provider.host_key_fingerprint, message)
        self.assertIn('Reset Pinned Host Key', message)

        # Unrelated errors pass through untouched
        plain = self.provider._describe_connection_error(ValueError('boom'))
        self.assertEqual(plain, 'boom')

    def test_action_reset_host_key(self):
        if not asyncssh:
            self.skipTest("asyncssh not installed")

        key = asyncssh.generate_private_key('ssh-ed25519')
        self.provider._pin_server_host_key(self._fake_conn_with_key(key))
        self.assertTrue(self.provider.server_host_key)

        action = self.provider.action_reset_host_key()

        self.assertFalse(self.provider.server_host_key)
        self.assertFalse(self.provider.host_key_fingerprint)
        self.assertEqual(action['tag'], 'display_notification')
        # After a reset the next connection is TOFU again
        self.assertIsNone(self.provider._get_connection_options()['known_hosts'])
