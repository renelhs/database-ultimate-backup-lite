# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

# Public store page of the paid "Database Ultimate Backup" (Full) edition.
FULL_EDITION_URL = "https://apps.odoo.com/apps/modules/18.0/database_ultimate_backup"


class BackupUpgradeTeaser(models.TransientModel):
    """In-app upsell screen for features that only exist in the Full edition.

    This model stores no real data: each menu entry that points to a feature
    the Lite edition does not ship (extra cloud providers, the live dashboard)
    opens a throwaway record whose content is built from the ``teaser_topic``
    context key. Nothing here touches or depends on the backup models.
    """

    _name = "backup.upgrade.teaser"
    _description = "Database Ultimate Backup - Full Edition Teaser"

    name = fields.Char(string="Title", readonly=True)
    body_html = fields.Html(string="Details", readonly=True, sanitize=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        topic = self.env.context.get("teaser_topic", "general")
        title, body = self._build_teaser(topic)
        res["name"] = title
        res["body_html"] = body
        return res

    @api.model
    def _build_teaser(self, topic):
        """Return ``(title, body_html)`` for the requested teaser topic."""
        provider_labels = {
            "aws_s3": _("Amazon S3"),
            "do_spaces": _("DigitalOcean Spaces"),
            "azure": _("Azure Blob Storage"),
            "gcs": _("Google Cloud Storage"),
            "gdrive": _("Google Drive"),
        }

        if topic == "dashboard":
            title = _("The real-time Dashboard is available in the Full Edition")
            intro = _(
                "The Full Edition adds a live monitoring dashboard so you can "
                "see the health of every backup at a glance."
            )
            bullets = [
                _("KPI tiles — backups created, total storage used and last-run status at a glance"),
                _("30-day success rate — spot reliability issues before they cost you a restore"),
                _("Storage totals — see how much space your backups use across every destination"),
                _("Trend charts — visualize backup volume and success over time"),
            ]
        else:
            provider = provider_labels.get(topic, _("Multi-cloud storage"))
            title = _("%s is available in the Full Edition", provider)
            intro = _(
                "%s is one of several cloud storage destinations included in the "
                "Full Edition of Database Ultimate Backup.",
                provider,
            )
            bullets = [
                _("Multi-cloud redundancy — store the same backup across several providers at once"),
                _("Parallel uploads — push to every destination simultaneously for faster off-site copies"),
                _("Server-side encryption — keep your backups protected at rest in the cloud"),
                _("Real-time dashboard — KPI tiles, 30-day success rate and storage trends"),
                _("Team alerts — Slack, Microsoft Teams, Telegram and webhook notifications"),
            ]

        items = "".join("<li>%s</li>" % bullet for bullet in bullets)
        footer = _(
            "Your Lite edition keeps working exactly as it does today — the Full "
            "Edition simply adds more storage destinations and monitoring."
        )
        body = (
            '<div class="alert alert-info" role="alert">%s</div>'
            '<ul class="mt-3">%s</ul>'
            '<p class="text-muted mt-3">%s</p>'
        ) % (intro, items, footer)
        return title, body

    def action_get_full_edition(self):
        """Open the Full edition's store page in a new browser tab."""
        return {
            "type": "ir.actions.act_url",
            "url": FULL_EDITION_URL,
            "target": "new",
        }
