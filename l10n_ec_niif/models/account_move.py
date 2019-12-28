# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from ..models import modules_mapping

class L10nECIdentificationType(models.Model):

    _name = 'l10n_ec.identification.type'

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True)
    document_type_ids = fields.Many2many('l10n_latam.document.type', string='Tipos de Transacciones Asociadas')
    sale_invoice_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                    string="Default Sales Document Type for Invoices", required=False, )
    sale_credit_note_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                        string="Default Sales Document Type for Credit Notes",
                                                        required=False, )
    sale_debit_note_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                       string="Default Sales Document Type for Debit Notes",
                                                       required=False, )
    purchase_invoice_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                        string="Default Purchases Document Type for Invoices",
                                                        required=False, )
    purchase_credit_note_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                            string="Default Purchases Document Type for Credit Notes",
                                                            required=False, )
    purchase_debit_note_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                           string="Default Purchases Document Type for Debit Notes",
                                                           required=False, )
    purchase_liquidation_document_type_id = fields.Many2one(comodel_name="l10n_latam.document.type",
                                                            string="Default Document Type for Purchase's Liquidation",
                                                            required=False, )

    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        recs = self.browse()
        res = super(L10nECIdentificationType, self)._name_search(name, args, operator, limit, name_get_uid)
        if not res and name:
            recs = self.search([('name', operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search([('code', operator, name)] + args, limit=limit)
            if recs:
                res = models.lazy_name_get(self.browse(recs.ids).with_user(name_get_uid)) or []
        return res

    def name_get(self):
        res = []
        for r in self:
            name = "%s - %s" % (r.code, r.name)
            res.append((r.id, name))
        return res

class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ec_tax_support_id = fields.Many2one(comodel_name="l10n_ec.tax.support",
                                             string="Tax Support", required=False, )
    l10n_ec_is_exportation = fields.Boolean(string="Is Exportation?")
    l10n_ec_tipo_regimen_pago_exterior = fields.Selection([
        ('01', 'Régimen general'),
        ('02', 'Paraíso fiscal'),
        ('03', 'Régimen fiscal preferente o jurisdicción de menor imposición')
        ], string='Tipo de regimen fiscal del exterior',
         states={}, help="")
    l10n_ec_aplica_convenio_doble_tributacion = fields.Selection([
        ('si', 'SI'),
        ('no','NO'),
        ], string='Aplica convenio doble tributación',
         states={}, help="")
    l10n_ec_pago_exterior_sujeto_retencion = fields.Selection([
        ('si', 'SI'),
        ('no','NO'),
        ], string='Pago sujeto a retención',
         states={}, help="")
    l10n_ec_foreign = fields.Boolean('Foreign?',
                                    related='partner_id.l10n_ec_foreign', store=True)
    l10n_ec_debit_note = fields.Boolean(string="Debit Note?")
    l10n_ec_liquidation = fields.Boolean(string="Liquidation of Purchases?")

    @api.depends(
        'partner_id.l10n_ec_type_sri',
        'l10n_ec_point_of_emission_id',
        'l10n_ec_is_exportation',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
        'type',
        'company_id',
    )
    def _get_l10n_ec_identification_type(self):
        def get_identification(code):
            identification_model = self.env['l10n_ec.identification.type']
            identification = identification_model.search([
                ('code', '=', code)
            ])
            return identification and identification.id or False
        tax_support_model = self.env['l10n_ec.tax.support']
        for move in self:
            if move.company_id.country_id.code == 'EC':
                supports = tax_support_model.browse()
                if move.partner_id.l10n_ec_type_sri:
                    if move.type in ('in_invoice', 'in_refund'):
                        if move.partner_id.l10n_ec_type_sri == 'Ruc':
                            move.l10n_ec_identification_type_id = get_identification('01')
                        elif move.partner_id.l10n_ec_type_sri == 'Cedula':
                            move.l10n_ec_identification_type_id = get_identification('02')
                        elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                            move.l10n_ec_identification_type_id = get_identification('03')
                        else:
                            move.l10n_ec_identification_type_id = False
                    elif move.type in ('out_invoice', 'out_refund'):
                        if not move.l10n_ec_is_exportation:
                            if move.partner_id.l10n_ec_type_sri == 'Ruc':
                                move.l10n_ec_identification_type_id = get_identification('04')
                            elif move.partner_id.l10n_ec_type_sri == 'Cedula':
                                move.l10n_ec_identification_type_id = get_identification('05')
                            elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                                move.l10n_ec_identification_type_id = get_identification('06')
                            elif move.partner_id.l10n_ec_type_sri == 'Consumidor':
                                move.l10n_ec_identification_type_id = get_identification('07')
                            else:
                                move.l10n_ec_identification_type_id = False
                        else:
                            if move.partner_id.l10n_ec_type_sri == 'Ruc':
                                move.l10n_ec_identification_type_id = get_identification('20')
                            elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                                move.l10n_ec_identification_type_id = get_identification('21')
                            else:
                                move.l10n_ec_identification_type_id = False
                else:
                    move.l10n_ec_identification_type_id = False
                if move.l10n_ec_identification_type_id:
                    latam_type = 'invoice'
                    if move.type in ('out_refund', 'in_refund'):
                        latam_type = 'credit_note'
                    move.write({
                        'l10n_latam_available_document_type_ids': [(6, 0, move.l10n_ec_identification_type_id.
                                                                    document_type_ids.filtered(
                            lambda x: x.internal_type == latam_type).ids)]
                    })
                    if move.l10n_latam_available_document_type_ids and \
                            move.l10n_latam_document_type_id.id not in move.l10n_latam_available_document_type_ids.ids:
                        if move.type == 'in_invoice':
                            move.l10n_latam_document_type_id = move.purchase_invoice_document_type_id.id
                        elif move.type == 'in_refund':
                            move.l10n_latam_document_type_id = move.purchase_credit_note_document_type_id.id
                        elif move.type == 'out_invoice':
                            move.l10n_latam_document_type_id = move.sale_invoice_document_type_id.id
                        elif move.type == 'out_refund':
                            move.l10n_latam_document_type_id = move.sale_credit_note_document_type_id.id
                    if move.l10n_latam_document_type_id:
                        supports = tax_support_model.search([
                            ('document_type_ids', 'in', move.l10n_latam_document_type_id.ids)
                        ])
                else:
                    move.write({
                        'l10n_latam_available_document_type_ids': []
                    })
                if supports:
                    move.write({
                        'l10n_ec_tax_support_domain_ids': [(6, 0, supports.ids)]
                    })
                else:
                    move.write({
                        'l10n_ec_tax_support_domain_ids': []
                    })

    l10n_ec_identification_type_id = fields.Many2one('l10n_ec.identification.type',
                                                     string="Ecuadorian Identification Type",
                                                     store=True, compute='_get_l10n_ec_identification_type')
    l10n_ec_tax_support_domain_ids = fields.Many2many(comodel_name="l10n_ec.tax.support",
                                                      string="Tax Support Domain",
                                                      compute='_get_l10n_ec_identification_type')

    l10n_ec_point_of_emission_id = fields.Many2one(comodel_name="l10n_ec.point.of.emission",
                                                   string="Point of Emission", readonly=True,
                                                   states={'draft': [('readonly', False)]})
    l10n_ec_agency_id = fields.Many2one(comodel_name="l10n_ec.agency",
                                        string="Agency", related="l10n_ec_point_of_emission_id.agency_id", store=True,
                                        readonly=True)
    l10n_ec_authorization_line_id = fields.Many2one(comodel_name="l10n_ec.sri.authorization.line",
                                                    string="Own Ecuadorian Authorization Line")
    l10n_ec_authorization_id = fields.Many2one(comodel_name="l10n_ec.sri.authorization",
                                               string="Own Ecuadorian Authorization",
                                               related="l10n_ec_authorization_line_id.authorization_id", store=True)
    l10n_ec_type_emission = fields.Selection(string="Type Emission",
                                             selection=[
                                                 ('electronic', 'Electronic'),
                                                 ('pre_printed', 'Pre Printed'),
                                                 ('auto_printer', 'Auto Printer'),
                                             ],
                                             required=False)
    @api.depends(
        'name',
        'l10n_latam_document_type_id',
    )
    def _compute_l10n_ec_document_number(self):
        recs_with_name = self.filtered(lambda x: x.name != '/' and x.company_id.country_id.code == 'EC')
        for rec in recs_with_name:
            name = rec.name
            doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
            if doc_code_prefix and name:
                name = name.split(" ", 1)[-1]
            rec.l10n_ec_document_number = name
        remaining = self - recs_with_name
        remaining.l10n_ec_document_number = False

    l10n_ec_document_number = fields.Char(string="Ecuadorian Document Number",
                                          readonly=True, compute="_compute_l10n_ec_document_number", store=True)


    @api.model
    def default_get(self, fields):
        values = super(AccountMove, self).default_get(fields)
        if 'type' in fields:
            default_printer_default = self.env['res.users']. \
                get_default_point_of_emission(self.env.user.id, raise_exception=True).get('default_printer_default_id')
            values['l10n_ec_point_of_emission_id'] = default_printer_default.id
            if default_printer_default:
                values['l10n_ec_type_emission'] = default_printer_default.type_emission
        return values

    @api.onchange(
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
        'l10n_ec_point_of_emission_id',
    )
    def _onchange_point_of_emission(self):
        for move in self.filtered(lambda x: x.company_id.country_id.code == 'EC' and x.type in ('out_invoice', 'out_refund')):
            if move.l10n_ec_point_of_emission_id:
                invoice_type = modules_mapping.get_invoice_type(move.type, move.l10n_ec_debit_note,
                                                                move.l10n_ec_liquidation)
                next_number, auth_line = move.l10n_ec_point_of_emission_id.get_next_value_sequence(invoice_type, False, False)
                if next_number:
                    move.l10n_latam_document_number = next_number
                if auth_line:
                    move.l10n_ec_authorization_line_id = auth_line.id

AccountMove()

