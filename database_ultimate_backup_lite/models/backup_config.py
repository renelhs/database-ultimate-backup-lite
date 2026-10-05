# -*- coding: utf-8 -*-

import datetime
import json
import logging
import re

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from .backup_utils import require_backup_admin, confined_path, utc_datetime

_logger = logging.getLogger(__name__)


class BackupConfig(models.Model):
    """
    Main backup configuration model.
    
    This model defines backup configurations with support for multiple
    storage providers, scheduling, and advanced features.
    """
    _name = 'backup.config'
    _description = 'Backup Configuration'
    _order = 'name, id desc'
    
    # Basic configuration
    name = fields.Char(
        string='Name',
        required=True,
        help='Human-readable name for this backup configuration'
    )
    description = fields.Text(
        string='Description',
        help='Optional description for this backup configuration'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this backup configuration is active'
    )
    
    # Database configuration
    database_name = fields.Char(
        string='Database Name',
        required=True,
        default=lambda self: self._get_current_database(),
        help='Name of the database to backup'
    )
    backup_format = fields.Selection([
        ('zip', 'ZIP Archive'),
        ('dump', 'PostgreSQL Dump (custom format, no filestore)'),
    ], string='Backup Format', required=True, default='zip',
       help='Format of the backup file')
    include_filestore = fields.Boolean(
        string='Include Filestore',
        default=True,
        help='Include attachments in ZIP backups. PostgreSQL dumps never include the filestore.'
    )
    
    # Storage providers
    local_provider_ids = fields.Many2many(
        'backup.provider.local',
        'backup_config_local_provider_rel',
        'config_id', 'provider_id',
        string='Local Storage Providers',
        help='Local filesystem storage providers'
    )
    sftp_provider_ids = fields.Many2many(
        'backup.provider.sftp',
        'backup_config_sftp_provider_rel',
        'config_id', 'provider_id',
        string='SFTP Storage Providers',
        help='SFTP/SSH remote storage providers'
    )
    # Retention policy
    retention_policy = fields.Selection([
        ('count', 'Keep Last N Backups'),
        ('days', 'Keep Backups for N Days'),
        ('custom', 'Keep All Backups (No Automatic Deletion)'),
    ], string='Retention Policy', required=True, default='count')
    retention_count = fields.Integer(
        string='Number of Backups to Keep',
        default=7,
        help='Number of recent backups to keep (for count-based retention)'
    )
    retention_days = fields.Integer(
        string='Days to Keep Backups',
        default=30,
        help='Number of days to keep backups (for time-based retention)'
    )
    # Advanced options
    backup_name_template = fields.Char(
        string='Backup Name Template',
        default='{database}_{timestamp}.{format}',
        help='Template for backup filenames. Available variables: {database}, {timestamp}, {format}'
    )
    verify_backups = fields.Boolean(
        string='Verify Backup Integrity',
        default=True,
        help='Verify backup integrity after creation and upload'
    )
    
    # Notifications
    notify_success = fields.Boolean(
        string='Notify on Success',
        default=False,
        help='Send notification when backup completes successfully'
    )
    notify_failure = fields.Boolean(
        string='Notify on Failure',
        default=True,
        help='Send notification when the backup fails or some storage destinations fail'
    )
    notification_emails = fields.Char(
        string='Notification Emails',
        help='Comma-separated list of email addresses for notifications'
    )
    
    # Statistics and monitoring
    last_backup_date = fields.Datetime(
        string='Last Backup Date',
        readonly=True
    )
    last_backup_status = fields.Selection([
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
    ], string='Last Backup Status', readonly=True)
    last_backup_message = fields.Text(
        string='Last Backup Message',
        readonly=True
    )
    total_backups_created = fields.Integer(
        string='Total Backups Created',
        default=0,
        readonly=True
    )
    backup_success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True,
        help='Success rate based on backup job history'
    )

    # Relationship to backup jobs
    backup_job_ids = fields.One2many(
        'backup.job',
        'config_id',
        string='Backup Jobs',
        readonly=True
    )

    @property
    def all_providers(self):
        """Get all configured providers."""
        return list(self.local_provider_ids.filtered('active')) + list(self.sftp_provider_ids.filtered('active'))

    def _get_current_database(self):
        """Get current database name."""
        return self.env.cr.dbname
    
    @api.depends('backup_job_ids.status')
    def _compute_success_rate(self):
        """Compute backup success rate."""
        for record in self:
            jobs = record.backup_job_ids
            if jobs:
                successful_jobs = jobs.filtered(lambda j: j.status == 'success')
                record.backup_success_rate = (len(successful_jobs) / len(jobs)) * 100
            else:
                record.backup_success_rate = 0.0
    
    def create_backup(self):
        """Queue a durable job for the dedicated backup worker."""
        require_backup_admin(self)
        self.ensure_one()
        if not self.active or not self.all_providers:
            raise UserError("An active configuration with active storage providers is required.")
        # Force a write conflict under Odoo's repeatable-read isolation. A request
        # with an older snapshot must retry before checking for pending jobs.
        # No field value changes; a row lock alone still allows duplicate inserts.
        self.env.cr.execute('UPDATE backup_config SET write_date = write_date WHERE id = %s', [self.id])
        Job = self.env['backup.job']
        if Job.search_count([('config_id', '=', self.id), ('status', 'in', ['pending', 'running'])]):
            raise UserError("This configuration already has a queued or running backup.")
        job = Job.create({
            'config_id': self.id,
            'database_name': self.database_name,
            'backup_format': self.backup_format,
            'include_filestore': self.backup_format == 'zip' and self.include_filestore,
            'status': 'pending',
            'is_manual': self.env.context.get('manual_execution', True),
        })
        # This fixed cron is an implementation detail; backup administrators do
        # not need access to Odoo's technical Scheduled Actions settings.
        runner = self.env.ref('database_ultimate_backup_lite.backup_job_cron').sudo()
        if not runner.active:
            raise UserError("Enable the Database Ultimate Backup Lite Job Queue scheduled action first.")
        runner._trigger()
        if not self.env.context.get('manual_execution', True):
            return job
        return {
            'type': 'ir.actions.act_window',
            'name': 'Queued Backup',
            'res_model': 'backup.job',
            'res_id': job.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def test_providers(self):
        """Test all configured providers."""
        require_backup_admin(self)
        self.ensure_one()
        
        if not self.all_providers:
            raise UserError("No storage providers configured")
        
        results = []
        
        for provider in self.all_providers:
            try:
                result = provider.test_connection()
                results.append({
                    'provider': provider.name,
                    'success': result.get('success', False),
                    'message': result.get('message', 'Unknown error')
                })
            except Exception as e:
                results.append({
                    'provider': provider.name,
                    'success': False,
                    'message': str(e)
                })
        
        # Create summary message
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        if failed:
            # Some providers failed
            message_parts = []
            if successful:
                message_parts.append(f"Successful ({len(successful)}):")
                message_parts.extend([f"✓ {r['provider']}: {r['message']}" for r in successful])
                message_parts.append("")  # Empty line
            
            message_parts.append(f"Failed ({len(failed)}):")
            message_parts.extend([f"✗ {r['provider']}: {r['message']}" for r in failed])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Provider Test Results',
                    'message': '\n'.join(message_parts),
                    'type': 'warning',
                    'sticky': True,
                }
            }
        else:
            # All providers successful
            message_parts = [f"All provider tests successful! ({len(successful)})", ""]
            message_parts.extend([f"✓ {r['provider']}: {r['message']}" for r in successful])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Provider Tests Successful',
                    'message': '\n'.join(message_parts),
                    'type': 'success',
                    'sticky': False,
                }
            }
    
    def test_retention_policy(self):
        """Test retention policy without actually deleting backups."""
        require_backup_admin(self)
        self.ensure_one()
        
        results = []
        
        for provider in self.all_providers:
            try:
                # Get list of backups
                backups = self._get_owned_backups(provider)
                
                # Determine which backups would be deleted
                backups_to_delete = self._get_backups_to_delete(backups)
                
                results.append({
                    'provider': provider.name,
                    'success': True,
                    'total_backups': len(backups),
                    'backups_to_delete': len(backups_to_delete),
                    'backups_to_keep': len(backups) - len(backups_to_delete),
                    'deletion_list': [b['filename'] for b in backups_to_delete[:5]]  # Show first 5
                })
                
            except Exception as e:
                results.append({
                    'provider': provider.name,
                    'success': False,
                    'error': str(e),
                    'total_backups': 0,
                    'backups_to_delete': 0,
                    'backups_to_keep': 0,
                    'deletion_list': []
                })
        
        # Create summary message
        message_parts = [f"Retention Policy Test Results ({self.retention_policy}):", ""]
        
        if self.retention_policy == 'count':
            message_parts.append(f"Policy: Keep last {self.retention_count} backups")
        elif self.retention_policy == 'days':
            message_parts.append(f"Policy: Keep backups for {self.retention_days} days")
        else:
            message_parts.append("Policy: Keep all backups (no cleanup)")
        
        message_parts.append("")
        
        for result in results:
            if result['success']:
                message_parts.append(f"✓ {result['provider']}:")
                message_parts.append(f"  Total backups: {result['total_backups']}")
                message_parts.append(f"  Would delete: {result['backups_to_delete']}")
                message_parts.append(f"  Would keep: {result['backups_to_keep']}")
                if result['deletion_list']:
                    message_parts.append(f"  Files to delete: {', '.join(result['deletion_list'])}")
                    if result['backups_to_delete'] > 5:
                        message_parts.append(f"    ... and {result['backups_to_delete'] - 5} more")
            else:
                message_parts.append(f"✗ {result['provider']}: {result['error']}")
            message_parts.append("")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Retention Policy Test',
                'message': '\n'.join(message_parts),
                'type': 'info',
                'sticky': True,
            }
        }
    
    def cleanup_old_backups(self):
        """Clean up old backups according to retention policy."""
        require_backup_admin(self)
        self.ensure_one()
        
        is_manual = self.env.context.get('manual_execution', True)
        results = []
        total_deleted = 0
        
        for provider in self.all_providers:
            try:
                # Get list of backups
                backups = self._get_owned_backups(provider)
                
                # Determine which backups to delete
                backups_to_delete = self._get_backups_to_delete(backups)
                
                deleted_count = 0
                failed_count = 0
                
                # Delete old backups
                for backup in backups_to_delete:
                    result = provider.delete_backup(backup['filename'], backup_info=backup)
                    if result.get('success'):
                        deleted_count += 1
                        _logger.info(
                            "Deleted old backup %s from provider %s", 
                            backup['filename'], provider.name
                        )
                    else:
                        failed_count += 1
                        _logger.warning(
                            "Failed to delete backup %s from provider %s: %s",
                            backup['filename'], provider.name, result.get('message', 'Unknown error')
                        )
                
                results.append({
                    'provider': provider.name,
                    'success': True,
                    'deleted': deleted_count,
                    'failed': failed_count,
                    'total_backups': len(backups)
                })
                total_deleted += deleted_count
                
            except Exception as e:
                _logger.error(
                    "Error cleaning up backups for provider %s: %s",
                    provider.name, str(e)
                )
                results.append({
                    'provider': provider.name,
                    'success': False,
                    'error': str(e),
                    'deleted': 0,
                    'failed': 0,
                    'total_backups': 0
                })
        
        # Return notification for manual execution
        if is_manual:
            # Create summary message
            message_parts = [f"Cleanup completed! Policy: {self.retention_policy}", ""]
            
            if self.retention_policy == 'count':
                message_parts.append(f"Keeping last {self.retention_count} backups per provider")
            elif self.retention_policy == 'days':
                message_parts.append(f"Keeping backups for {self.retention_days} days")
            else:
                message_parts.append("Keeping all backups; no files will be deleted")
            
            message_parts.extend(["", f"Total files deleted: {total_deleted}", ""])
            
            for result in results:
                if result['success']:
                    message_parts.append(f"✓ {result['provider']}:")
                    message_parts.append(f"  Total backups: {result['total_backups']}")
                    message_parts.append(f"  Deleted: {result['deleted']}")
                    if result['failed'] > 0:
                        message_parts.append(f"  Failed: {result['failed']}")
                else:
                    message_parts.append(f"✗ {result['provider']}: {result['error']}")
                message_parts.append("")
            
            notification_type = 'success' if total_deleted > 0 else 'info'
            if any(not r['success'] for r in results):
                notification_type = 'warning'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Backup Cleanup Results',
                    'message': '\n'.join(message_parts),
                    'type': notification_type,
                    'sticky': True,
                }
            }
    
    def _get_backups_to_delete(self, backups):
        if self.retention_policy == 'custom' or not backups:
            return []
        dated = [(backup, utc_datetime(backup.get('created_date') or backup.get('modified_date')))
                 for backup in backups]
        # Unknown dates are preserved, and every destination keeps its latest known copy.
        dated = sorted(((backup, date) for backup, date in dated if date),
                       key=lambda item: item[1], reverse=True)
        if self.retention_policy == 'count':
            return [backup for backup, _date in dated[max(1, self.retention_count):]]
        cutoff = fields.Datetime.now() - datetime.timedelta(days=self.retention_days)
        return [backup for backup, date in dated[1:] if date < cutoff]
    
    def _update_backup_statistics(self, result):
        """Update backup statistics after a backup operation."""
        backup_job = result.get('backup_job')
        status = backup_job.status if backup_job else ('success' if result.get('success') else 'error')
        message = result.get('message', 'Unknown result')
        
        vals = {
            'last_backup_date': fields.Datetime.now(),
            'last_backup_status': status,
            'last_backup_message': message,
        }
        
        if result.get('success'):
            vals['total_backups_created'] = self.total_backups_created + 1
        
        self.write(vals)

    def _send_notification(self, backup_job, notification_type):
        """
        Send backup notification email.

        This method runs independently from the backup process to ensure
        email failures don't affect the backup job status.
        """
        event = 'warning' if backup_job.status == 'warning' else notification_type
        enabled = self.notify_success if event == 'success' else self.notify_failure
        if not enabled or not self.notification_emails:
            _logger.debug("Skipping notification: no recipient emails configured")
            return

        try:
            # Check if mail server is configured
            mail_server = self.env['ir.mail_server'].sudo().search([], order='sequence asc', limit=1)
            if not mail_server:
                _logger.warning("Cannot send backup notification: no mail server configured in Odoo")
                return

            # Prepare email content
            if event == 'success':
                subject = "Backup Successful: %s" % self.name
                body = self._get_success_notification_body(backup_job)
            elif event == 'warning':
                subject = "Backup Completed with Warnings: %s" % self.name
                body = (
                    "The backup was created, but some storage destinations failed.\n\n"
                    "Configuration: %s\nDatabase: %s\nBackup: %s\n\nDetails: %s"
                    % (self.name, backup_job.database_name, backup_job.backup_filename,
                       backup_job.error_message)
                )
            else:
                subject = "Backup Failed: %s" % self.name
                body = self._get_failure_notification_body(backup_job)

            # Get sender email
            catch_all_domain = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")
            system_email = self.env["ir.config_parameter"].sudo().get_param("mail.default.from")
            sender_email = (
                f"backup@{catch_all_domain}" if catch_all_domain
                else system_email if system_email
                else mail_server.smtp_user
            )

            # Validate sender email
            if not sender_email:
                _logger.warning("Cannot send backup notification: no valid sender email address")
                return

            # Parse recipient emails
            recipient_emails = [email.strip() for email in self.notification_emails.split(',') if email.strip()]
            if not recipient_emails:
                _logger.warning("Cannot send backup notification: no valid recipient emails")
                return

            # Build and send email
            _logger.info("Sending backup notification email from %s to %s", sender_email, recipient_emails)
            msg = mail_server._build_email__(
                sender_email,
                recipient_emails,
                subject,
                body
            )
            mail_server.send_email(msg)
            _logger.info("Backup notification sent successfully")
        except Exception as e:
            # Log detailed error but don't raise - email failures shouldn't affect backup success
            _logger.warning(
                "Failed to send backup notification for job %s (Status: %s). "
                "Error: %s. The backup itself completed successfully, but email notification failed. "
                "Please check your mail server configuration.",
                backup_job.id, notification_type, str(e)
            )

    @staticmethod
    def _format_duration(duration_seconds):
        """
        Format duration in a human-readable format.

        Args:
            duration_seconds: Duration in seconds (float)

        Returns:
            Formatted string with appropriate unit (e.g., "45 seconds", "2.5 minutes", "1.2 hours")
        """
        if not duration_seconds:
            return 'Unknown'

        # Less than 60 seconds: show as seconds (no decimals)
        if duration_seconds < 60:
            return f"{int(duration_seconds)} seconds"
        # Less than 60 minutes: show as minutes (1 decimal if needed)
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            # Show 1 decimal only if not a whole number
            if minutes == int(minutes):
                return f"{int(minutes)} minutes"
            else:
                return f"{minutes:.1f} minutes"
        # 60 minutes or more: show as hours (1 decimal if needed)
        else:
            hours = duration_seconds / 3600
            # Show 1 decimal only if not a whole number
            if hours == int(hours):
                return f"{int(hours)} hours"
            else:
                return f"{hours:.1f} hours"
    
    def _get_success_notification_body(self, backup_job):
        """Generate success notification email body."""
        return ("""
            Backup completed successfully!
            
            Configuration: %(config_name)s
            Database: %(database)s
            Format: %(format)s
            Start Time: %(start_time)s
            End Time: %(end_time)s
            Duration: %(duration)s
            Size: %(size)s
            
            Backup Details:
            %(details)s
            
            Best regards,
            Odoo Backup System
        """ % {
            'config_name': self.name,
            'database': self.database_name,
            'format': self.backup_format.upper(),
            'start_time': backup_job.start_time.strftime('%Y-%m-%d %H:%M:%S') if backup_job.start_time else 'Unknown',
            'end_time': backup_job.end_time.strftime('%Y-%m-%d %H:%M:%S') if backup_job.end_time else 'Unknown',
            'duration': self._format_duration(backup_job.duration),
            'size': backup_job.backup_size_human or 'Unknown',
            'details': backup_job.backup_details or 'No additional details',
        })
    
    def _get_failure_notification_body(self, backup_job):
        """Generate failure notification email body."""
        return ("""
            Backup failed!
            
            Configuration: %(config_name)s
            Database: %(database)s
            Format: %(format)s
            Start Time: %(start_time)s
            Error Time: %(end_time)s
            
            Error Details:
            %(error_message)s
            
            Please check the backup configuration and try again.
            
            Best regards,
            Odoo Backup System
        """ % {
            'config_name': self.name,
            'database': self.database_name,
            'format': self.backup_format.upper(),
            'start_time': backup_job.start_time.strftime('%Y-%m-%d %H:%M:%S') if backup_job.start_time else 'Unknown',
            'end_time': backup_job.end_time.strftime('%Y-%m-%d %H:%M:%S') if backup_job.end_time else 'Unknown',
            'error_message': backup_job.error_message or 'Unknown error',
        })
    
    # Validation methods
    @api.constrains('active', 'local_provider_ids', 'sftp_provider_ids')
    def _check_providers(self):
        """Ensure at least one provider is configured for active configurations."""
        for record in self:
            # Only validate when activating a configuration (not during installation)
            if (record.active and 
                not self.env.context.get('install_mode') and
                not self.env.context.get('module_installation') and
                len(record.all_providers) == 0):
                raise ValidationError("At least one storage provider must be configured for active backup configurations")

    @api.constrains('retention_count', 'retention_policy')
    def _check_retention_count(self):
        """Validate retention count."""
        for record in self:
            if record.retention_policy == 'count' and record.retention_count < 1:
                raise ValidationError("Retention count must be at least 1")
    
    @api.constrains('retention_days', 'retention_policy')
    def _check_retention_days(self):
        """Validate retention days."""
        for record in self:
            if record.retention_policy == 'days' and record.retention_days < 1:
                raise ValidationError("Retention days must be at least 1")
    
    @api.constrains('notification_emails')
    def _check_notification_emails(self):
        """Validate notification email format."""
        for record in self:
            if record.notification_emails:
                emails = [email.strip() for email in record.notification_emails.split(',')]
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                
                for email in emails:
                    if email and not re.match(email_pattern, email):
                        raise ValidationError("Invalid email address: %s" % email)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate configuration."""
        for vals in vals_list:
            if not vals.get('database_name'):
                vals['database_name'] = self._get_current_database()
        
        return super().create(vals_list)
    
    # Scheduled action method
    @api.model
    @api.private
    def run_scheduled_backups(self):
        require_backup_admin(self)
        for config in self.search([('active', '=', True)]):
            try:
                with self.env.cr.savepoint():
                    config.with_context(manual_execution=False).create_backup()
            except Exception:
                _logger.exception("Unable to queue backup for %s", config.name)


    def _finish_backup(self, job, result):
        self._update_backup_statistics(result)
        event = 'failure' if job.status == 'error' else job.status
        try:
            with self.env.cr.savepoint():
                self._send_notification(job, event)
        except Exception:
            _logger.exception('Notification failed for backup job %s', job.id)
        if job.status in ('success', 'warning'):
            try:
                with self.env.cr.savepoint():
                    self.with_context(manual_execution=False).cleanup_old_backups()
            except Exception:
                _logger.exception('Retention cleanup failed for backup job %s', job.id)


    @staticmethod
    def _backup_location(info, provider=None):
        for key in ('file_id', 'full_path', 'file_path', 'remote_path', 'blob_path', 'blob_name'):
            if info.get(key):
                location = str(info[key])
                if provider is not None and provider._name == 'backup.provider.local':
                    try:
                        return confined_path(provider.backup_directory, location)
                    except ValidationError:
                        return None
                return location
        return None


    def _get_owned_backups(self, provider):
        """Only successful, recorded uploads of THIS configuration may be aged out."""
        owned = set()
        Job = self.env['backup.job']
        provider_key = f'{provider._name}:{provider.id}'
        for job in Job.search([('config_id', '=', self.id), ('status', 'in', ['success', 'warning'])]):
            try:
                results = json.loads(job.provider_results or '{}')
                result = results.get(provider_key) or results.get(provider.name) or {}
                metadata = result.get('metadata') or {}
                location = self._backup_location(metadata, provider)
                if result.get('success') and location:
                    owned.add((job.backup_filename, location))
            except (ValueError, TypeError, AttributeError):
                continue  # Unknown history never grants permission to delete a remote file.
        if not owned:
            return []
        # Legacy filenames can collide between configurations. Preserve ambiguous objects.
        names = list({name for name, _location in owned})
        for other in Job.search([('config_id', '!=', self.id), ('backup_filename', 'in', names)]):
            try:
                results = json.loads(other.provider_results or '{}')
                # Separate provider records may point at the same physical directory
                # or bucket. In ambiguous legacy history, preserve the object.
                for result in results.values():
                    location = self._backup_location(result.get('metadata') or {}, provider)
                    if location:
                        owned.discard((other.backup_filename, location))
            except (ValueError, TypeError, AttributeError):
                continue
        return [backup for backup in provider.list_backups()
                if (backup['filename'], self._backup_location(backup, provider)) in owned]
