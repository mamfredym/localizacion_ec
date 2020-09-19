from odoo import fields, models


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    l10n_ec_no_account = fields.Boolean(u"Not Required to Keep Accounting?")
