# -*- coding: UTF-8 -*- #

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import Warning, RedirectWarning, ValidationError

class ResUsers(models.Model):

    _inherit = 'res.users'

    l10n_ec_agency_ids = fields.Many2many('l10n_ec.agency', string='Allowed Agencies')
    l10n_ec_printer_default_id = fields.Many2one('l10n_ec.point.of.emission', string='Default Point of Emission')


ResUsers()
