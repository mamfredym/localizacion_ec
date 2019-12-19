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
    printer_point_ids = fields.One2many('l10n_ec.point.of.emission', 'agency_id', 'Points of Emission')
    user_ids = fields.Many2many('res.users', string='Allowed Users', help="", domain=[('share', '=', False)])
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
    type_emission = fields.Selection(string="Type Emission",
                                     selection=[
                                         ('electronic', 'Electronic'),
                                         ('pre_printed', 'Pre Printed'),
                                         ('auto_printer', 'Auto Printer'),
                                     ],
                                     required=True, default='electronic')
    sequence_ids = fields.One2many(comodel_name="l10n_ec.point.of.emission.document.sequence",
                                   inverse_name="printer_id", string="Initial Sequences", required=False, )

    @api.model
    def default_get(self, fields):
        values = super(L10EcPointOfEmission, self).default_get(fields)
        values['sequence_ids'] = [
            (0, 0, {'document_type': 'invoice', 'initial_sequence': 1}),
            (0, 0, {'document_type': 'withholding', 'initial_sequence': 1}),
            (0, 0, {'document_type': 'liquidation', 'initial_sequence': 1}),
            (0, 0, {'document_type': 'credit_note', 'initial_sequence': 1}),
            (0, 0, {'document_type': 'debit_note', 'initial_sequence': 1}),
            (0, 0, {'document_type': 'delivery_note', 'initial_sequence': 1}),
        ]
        return values

    def name_get(self):
        res = []
        full_name = self.env.context.get('full_name', True)
        for printer in self:
            name = "%s-%s %s" % (printer.agency_id and printer.agency_id.number or '', printer.number,
                                 full_name and printer.agency_id and printer.agency_id.name or '')
            res.append((printer['id'], name))
        return res

    _sql_constraints = [
        ('number_uniq', 'unique (number, agency_id)', _('The number of point of emission must be unique by Agency!')),
    ]


L10EcPointOfEmission()


class L10EcPointOfEmissionDocumentSequence(models.Model):

    _name = 'l10n_ec.point.of.emission.document.sequence'

    printer_id = fields.Many2one(comodel_name="l10n_ec.point.of.emission",
                                 string="Printer", required=True, )
    initial_sequence = fields.Integer(string="Initial Sequence", required=True, default=1)
    document_type = fields.Selection(string="Document Type", selection=[
        ('invoice', _('Invoice')),
        ('withholding', _('Withhold')),
        ('liquidation', _('Liquidation of Purchases')),
        ('credit_note', _('Credit Note')),
        ('debit_note', _('Debit Note')),
        ('delivery_note', _('Delivery Note')),
    ], required=True, )


L10EcPointOfEmissionDocumentSequence()
