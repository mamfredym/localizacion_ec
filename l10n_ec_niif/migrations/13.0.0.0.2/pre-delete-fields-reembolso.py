from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    recs_to_unlink = env["ir.model.data"].search(
        [
            (
                "name",
                "in",
                [
                    "selection__l10n_ec_account_invoice_reembolso__document_type__electronic",
                    "selection__l10n_ec_account_invoice_reembolso__document_type__normal",
                ],
            )
        ]
    )
    if recs_to_unlink:
        recs_to_unlink.unlink()
