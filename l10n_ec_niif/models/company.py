# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.onchange('country_id')
    def onchange_country(self):
        """ Argentinian companies use round_globally as tax_calculation_rounding_method """
        for rec in self.filtered(lambda x: x.country_id == self.env.ref('base.ec')):
            rec.tax_calculation_rounding_method = 'round_globally'

    def _localization_use_documents(self):
        """ Argentinian localization use documents """
        self.ensure_one()
        return True if self.country_id == self.env.ref('base.ec') else super()._localization_use_documents()