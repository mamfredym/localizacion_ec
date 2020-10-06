import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    JournalModel = env["account.journal"]
    journals = JournalModel.search(
        [
            ("type", "in", ("sale", "=", "purchase")),
            ("company_id.country_id.code", "=", "EC"),
            ("l10n_latam_use_documents", "=", False),
        ]
    )
    journals.write(
        {"l10n_latam_use_documents": True,}
    )
    journals._onchange_type()
