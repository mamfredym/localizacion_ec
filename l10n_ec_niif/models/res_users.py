# -*- coding: UTF-8 -*- #

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import Warning, RedirectWarning, ValidationError

class ResUsers(models.Model):

    _inherit = 'res.users'

    l10n_ec_agency_ids = fields.Many2many('l10n_ec.agency', string='Allowed Agencies')
    l10n_ec_printer_default_id = fields.Many2one('l10n_ec.point.of.emission', string='Default Point of Emission')

    @api.model
    def get_default_point_of_emission(self, user_id=False, get_all=True, raise_exception=True):
        user = self.browse()
        if user_id:
            user = self.browse(user_id)
        else:
            user = self.env.user
        printer_model = self.env['l10n_ec.point.of.emission']
        res = {
            'default_printer_default_id': printer_model.browse(),
            'all_printer_ids': printer_model.browse(),
        }
        if user.l10n_ec_printer_default_id:
            res['default_printer_default_id'] |= user.l10n_ec_printer_default_id
            res['all_printer_ids'] |= user.l10n_ec_printer_default_id
        if not res or get_all:
            for agency in user.l10n_ec_agency_ids:
                for printer in agency.printer_point_ids:
                    res['all_printer_ids'] |= printer
        if not res and raise_exception and user.company_id.country_id.code == 'EC':
            raise Warning(_('Your user does not have the permissions '
                            'configured correctly (Agency, Point of emission), please check with the administrator'))
        return res


ResUsers()
