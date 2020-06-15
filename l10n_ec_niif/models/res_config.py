
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_ec_consumidor_final_limit = fields.Float(string="Invoice Sales Limit Final Consumer",
                                                  related="company_id.l10n_ec_consumidor_final_limit", readonly=False)

    l10n_ec_withhold_sale_iva_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales IVA Account',
        related="company_id.l10n_ec_withhold_sale_iva_account_id",
        readonly=False)

    l10n_ec_withhold_sale_iva_tag_id = fields.Many2one(
        comodel_name='account.account.tag',
        string='Withhold Sales IVA Account Tag',
        related="company_id.l10n_ec_withhold_sale_iva_tag_id",
        readonly=False)

    l10n_ec_withhold_sale_rent_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales Rent Account',
        related="company_id.l10n_ec_withhold_sale_rent_account_id",
        readonly=False)

    l10n_ec_withhold_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Withhold Journal',
        related="company_id.l10n_ec_withhold_journal_id",
        readonly=False)
