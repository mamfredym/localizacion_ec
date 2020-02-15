# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_ec_consumidor_final_limit = fields.Float(string="Invoice Sales Limit Final Consumer",
                                                  related="company_id.l10n_ec_consumidor_final_limit", readonly=False)

