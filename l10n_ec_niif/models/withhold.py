# -*- coding: utf-8 -*-
from odoo import fields, models, api, _

_STATES = {'draft': [('readonly', False)]}


class L10nEcWithhold(models.Model):

    _name = 'l10n_ec.withhold'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'Ecuadorian Withhold'
    _rec_name = 'number'
    _mail_post_access = 'read'
    _order = 'issue_date DESC, number DESC'

    company_id = fields.Many2one(
        'res.company',
        'Company',
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related="company_id.currency_id",
        store=True,)
    number = fields.Char(
        string='Number',
        required=True)
    state = fields.Selection(
        string='State',
        selection=[
            ('draft', 'Draft'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        readonly=True,
        default='draft')
    issue_date = fields.Date(
        string='Issue date',
        readonly=True,
        states=_STATES,
        required=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        readonly=True,
        ondelete="restrict",
        states=_STATES,
        required=True)
    commercial_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Commercial partner',
        readonly=True,
        ondelete="restrict",
        related="partner_id.commercial_partner_id",
        store=True)
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Related Document',
        readonly=True,
        states=_STATES,
        required=False)
    partner_authorization_id = fields.Many2one(
        comodel_name='l10n_ec.sri.authorization.supplier',
        string='Partner authorization',
        readonly=True,
        states=_STATES,
        required=False)
    type = fields.Selection(
        string='Type',
        selection=[
            ('sale', 'On Sales'),
            ('purchase', 'On Purchases'),
            ('credit_card', 'On Credit Card Liquidation'),
        ],
        required=True, readonly=True, deafult=lambda self: self.env.context.get('withhold_type', 'sale'))
    document_type = fields.Selection(
        string='Document type',
        selection=[('normal', 'Pre Printed / AutoPrinter'),
                   ('electronic', 'Electronic'), ],
        required=True,
        readonly=True,
        states=_STATES,
        default="electronic")
    electronic_authorization = fields.Char(
        string='Electronic authorization',
        size=49,
        readonly=True,
        states=_STATES,
        required=False)
    point_of_emission_id = fields.Many2one(
        comodel_name="l10n_ec.point.of.emission",
        string="Point of Emission",
        ondelete="restrict",
        readonly=True,
        states=_STATES)
    agency_id = fields.Many2one(
        comodel_name="l10n_ec.agency",
        string="Agency", related="point_of_emission_id.agency_id",
        ondelete="restrict",
        store=True,
        readonly=True)
    authorization_line_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization.line",
        string="Own Ecuadorian Authorization Line",
        ondelete="restrict",
        readonly=True,
        states=_STATES,)
    concept = fields.Char(
        string='Concept',
        readonly=True,
        states=_STATES,
        required=False)
    note = fields.Char(
        string='Note', 
        required=False)
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Account Move',
        ondelete="restrict",
        readonly=True)
    line_ids = fields.One2many(
        comodel_name='l10n_ec.withhold.line',
        inverse_name='withhold_id',
        string='Lines',
        readonly=True,
        states=_STATES,
        required=True)

    @api.depends(
        'line_ids.type',
        'line_ids.tax_amount',
    )
    def _get_tax_amount(self):
        for rec in self:
            rec.tax_iva = sum(i.tax_amount for i in rec.line_ids.filtered(lambda x: x.type == 'iva'))
            rec.tax_rent = sum(r.tax_amount for r in rec.line_ids.filtered(lambda x: x.type == 'rent'))

    tax_iva = fields.Float(
        string='Withhold IVA',
        compute="_get_tax_amount",
        store=True,
        readonly=True)
    tax_rent = fields.Float(
        string='Withhold Rent',
        compute="_get_tax_amount",
        store=True,
        readonly=True)


class L10nEcWithholdLine(models.Model):

    _name = 'l10n_ec.withhold.line'
    _description = 'Ecuadorian Withhold'

    withhold_id = fields.Many2one(
        comodel_name='l10n_ec.withhold',
        string='Withhold',
        required=True,
        ondelete="cascade",
        readonly=True,)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related="withhold_id.company_id",
        store=True
    )
    issue_date = fields.Date(
        string='Issue date',
        related="withhold_id.issue_date",
        store=True,
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Related Document',
        required=False
    )
    tax_id = fields.Many2one(
        comodel_name='account.tax',
        string='Tax',
        required=False)
    base_tag_id = fields.Many2one(
        comodel_name='account.account.tag',
        string='Base Tax Tag',
        readonly=True)
    tax_tag_id = fields.Many2one(
        comodel_name='account.account.tag',
        string='Tax Tax Tag',
        readonly=True)
    type = fields.Selection(
        string='Type',
        selection=[('iva', 'IVA'),
                   ('rent', 'Rent'), ],
        required=False, )
    partner_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Partner Currency',
        required=False)
    base_amount = fields.Float(
        string='Base Amount',
        currency_field="partner_currency_id",
        required=True)
    tax_amount = fields.Float(
        string='Withhold Amount',
        currency_field="partner_currency_id",
        required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related="withhold_id.currency_id",
        store=True,)
    base_amount_currency = fields.Monetary(
        string='Base Amount',
        required=True)
    tax_amount_currency = fields.Monetary(
        string='Withhold Amount',
        required=True)
