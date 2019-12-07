# -*- coding: UTF-8 -*- #

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import Warning, RedirectWarning, ValidationError


class L10nEcAgency(models.Model):

    _name = 'l10n_ec.agency'
    _description = 'Agencia'

    name = fields.Char('Agency Name', required=True, readonly=False, index=True)
    number = fields.Char(string='S.R.I. Number', size=3, required=True, readonly=False, index=True)
    printer_point_ids = fields.One2many('l10n_ec.point.of.emission', 'agency_id', 'Points of Emission', required=False,
                                        auto_join=True, help="", )
    user_ids = fields.Many2many('res.users', 'rel_user_l10n_ec_agency', 'shop_id', 'user_id',
                                string='Allowed Users', help="", domain=[('share', '=', False)])
    address_id = fields.Many2one('res.partner', 'Address', required=False, help="", )
    company_id = fields.Many2one('res.company', 'Company', required=False, help="",
                                 default=lambda self: self.env.user.company_id.id)
    partner_id = fields.Many2one('res.partner', string="Company's Partner",
                                 related="company_id.partner_id")
    active = fields.Boolean(string="Active?", default=True)

    @api.constrains('number')
    def _check_number(self):
        for agency in self:
            if agency.number:
                try:
                    number_int = int(agency.number)
                    if number_int < 1 or number_int > 999:
                        raise ValidationError(_("Number of agency must be between 1 and 999"))
                except ValueError as e:
                    raise ValidationError(_("Number of agency must be only numbers"))

    _sql_constraints = [
        ('number_uniq', 'unique (number, company_id)', _('Number of Agency must be unique by company!')),
    ]


L10nEcAgency()


class L10EcPointOfEmission(models.Model):

    _name = 'l10n_ec.point.of.emission'

    name = fields.Char("Point of emission's name", required=True, readonly=False, index=True)
    agency_id = fields.Many2one('l10n_ec.agency', 'Agency', required=False, index=True, auto_join=True)
    number = fields.Char('S.R.I. Number', size=3, required=True, readonly=False, index=True)
    active = fields.Boolean(string="Active?", default=True)

    def name_get(self):
        res = []
        full_name = self.env.context.get('full_name', True)
        for printer in self:
            name = "%s-%s %s" % (printer.shop_id and printer.shop_id.number or '', printer.number,
                                 full_name and printer.shop_id and printer.shop_id.name or '')
            res.append((printer['id'], name))
        return res

    _sql_constraints = [
        ('number_uniq', 'unique (number, agency_id)', _('The number of point of emission must be unique by Agency!')),
    ]


L10EcPointOfEmission()
