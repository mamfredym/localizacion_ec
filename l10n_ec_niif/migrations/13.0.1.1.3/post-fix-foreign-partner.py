import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    partner_model = env["res.partner"]
    move_model = env["account.move"]
    it_pasaporte = env.ref("l10n_ec_niif.it_pasaporte")
    current_partners = partner_model.search(
        [
            ("country_id.code", "=", "EC"),
            ("l10n_latam_identification_type_id", "=", it_pasaporte.id),
        ]
    )
    if current_partners:
        current_partners.write(
            {
                "l10n_latam_identification_type_id": it_pasaporte.id,
                "l10n_ec_foreign_type": "01",
            }
        )
        current_moves = move_model.search(
            [
                ("partner_id", "in", current_partners.ids),
                ("l10n_ec_identification_type_id", "=", False),
            ]
        )
        for company in current_moves.mapped("company_id"):
            current_moves.filtered(lambda x: x.company_id.id == company.id).write(
                {
                    "company_id": company.id,
                }
            )
