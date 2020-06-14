# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):

    _inherit = 'account.journal'

    l10n_ec_debit_note = fields.Boolean(string="Debit Note?")
    l10n_ec_liquidation = fields.Boolean(string="Liquidation of Purchases?")

    @api.depends(
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
    )
    def _get_l10n_ec_extended_type(self):
        for journal in self:
            if not journal.l10n_ec_debit_note and not journal.l10n_ec_liquidation:
                journal.l10n_ec_extended_type = journal.type
            else:
                if journal.type == 'sale':
                    if journal.l10n_ec_debit_note:
                        journal.l10n_ec_extended_type = 'debit_note_out'
                elif journal.type == 'purchase':
                    if journal.l10n_ec_debit_note and not journal.l10n_ec_liquidation:
                        journal.l10n_ec_extended_type = 'debit_note_in'
                    elif not journal.l10n_ec_debit_note and journal.l10n_ec_liquidation:
                        journal.l10n_ec_extended_type = 'liquidation'
                else:
                    journal.l10n_ec_extended_type = journal.type

    l10n_ec_extended_type = fields.Char(string="Extended Type",
                                        required=False, compute="_get_l10n_ec_extended_type", store=True)


AccountJournal()
