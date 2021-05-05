from odoo import models


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    def create_debit(self):
        res = super(AccountDebitNote, self).create_debit()
        new_ctx = dict(self.env.context, internal_type="debit_note")
        res["context"] = new_ctx
        return res
