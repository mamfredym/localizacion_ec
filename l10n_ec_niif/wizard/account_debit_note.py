from odoo import api, fields, models


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    def _prepare_default_values(self, move):
        default_values = super(AccountDebitNote, self)._prepare_default_values(move)
        default_values["l10n_ec_debit_note"] = True
        return default_values
