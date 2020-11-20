from odoo import fields, models


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    l10n_ec_sri_type = fields.Selection(
        [
            ("contado", "Contado"),
            ("credito", "Crédito"),
        ],
        string="Tipo SRI",
        default="credito",
        required=True,
    )
