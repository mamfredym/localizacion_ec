from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    MoveModel = env["account.move"]
    all_company = env["res.company"].search([])
    invoice_type = env.ref("l10n_ec_niif.ec_dt_18")
    for company in all_company:
        moves_with_out_identification = MoveModel.search(
            [
                ("type", "=", "out_invoice"),
                ("l10n_ec_identification_type_id", "=", False),
                ("company_id", "=", company.id),
            ]
        )
        moves_with_out_identification._compute_l10n_ec_identification_type()
        moves_with_out_type = MoveModel.search(
            [
                ("type", "=", "out_invoice"),
                ("l10n_latam_document_type_id.code", "!=", "18"),
                ("company_id", "=", company.id),
            ]
        )
        if not moves_with_out_type:
            continue
        params = {
            "new_document_id": invoice_type.id,
            "move_ids": tuple(moves_with_out_type.ids),
        }
        cr.execute(
            "UPDATE account_move SET l10n_latam_document_type_id = %(new_document_id)s WHERE id IN %(move_ids)s", params
        )
