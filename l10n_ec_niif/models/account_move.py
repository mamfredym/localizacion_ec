# Part of Odoo. See LICENSE file for full copyright and licensing details.
from xml.etree.ElementTree import SubElement

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round
from ..models import modules_mapping


class L10nECIdentificationType(models.Model):

    _name = 'l10n_ec.identification.type'

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True)
    document_type_ids = fields.Many2many(
        'l10n_latam.document.type', string='Tipos de Transacciones Asociadas')
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
        res = super(L10nECIdentificationType, self)._name_search(
            name, args, operator, limit, name_get_uid)
        if not res and name:
            recs = self.search([('name', operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search(
                    [('code', operator, name)] + args, limit=limit)
            if recs:
                res = models.lazy_name_get(self.browse(
                    recs.ids).with_user(name_get_uid)) or []
        return res

    def name_get(self):
        res = []
        for r in self:
            name = "%s - %s" % (r.code, r.name)
            res.append((r.id, name))
        return res


class AccountMove(models.Model):
    _inherit = ["account.move", "ln10_ec.common.document", "ln10_ec.common.document.electronic"]
    _name = "account.move"

    @api.depends('type', 'l10n_ec_point_of_emission_id', 'l10n_ec_debit_note', 'l10n_ec_liquidation')
    def _compute_ln10_ec_is_enviroment_production(self):
        xml_model = self.env['sri.xml.data']
        for invoice in self:
            if invoice.is_invoice():
                invoice_type = self.get_invoice_type(invoice.type, invoice.l10n_ec_debit_note, invoice.l10n_ec_liquidation)
                invoice.ln10_ec_is_enviroment_production = xml_model.ln10_ec_is_enviroment_production(invoice_type, invoice.l10n_ec_point_of_emission_id)
            else:
                invoice.ln10_ec_is_enviroment_production =False

    ln10_ec_is_enviroment_production = fields.Boolean('Es Ambiente de Produccion?',
                                              compute='_compute_ln10_ec_is_enviroment_production', store=True, index=True)
    l10n_ec_original_invoice_id = fields.Many2one(comodel_name='account.move',
                                                  string="Original Invoice")
    l10n_ec_credit_note_ids = fields.One2many(comodel_name="account.move",
                                              inverse_name="l10n_ec_original_invoice_id",
                                              string="Credit Notes", required=False, )
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
        ('no', 'NO'),
    ], string='Aplica convenio doble tributación',
        states={}, help="")
    l10n_ec_pago_exterior_sujeto_retencion = fields.Selection([
        ('si', 'SI'),
        ('no', 'NO'),
    ], string='Pago sujeto a retención',
         states={}, help="")
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment.method', 'SRI Payment Method',
        default=lambda self: self.env.company.l10n_ec_sri_payment_id)
    l10n_ec_foreign = fields.Boolean('Foreign?',
        related='partner_id.l10n_ec_foreign', store=True)
    l10n_ec_debit_note = fields.Boolean(string="Debit Note?",
        default=lambda self: self.env.context.get('default_l10n_ec_debit_note', False))
    l10n_ec_liquidation = fields.Boolean(string="Liquidation of Purchases?",
        default=lambda self: self.env.context.get('default_l10n_ec_liquidation', False))

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
                supports = tax_support_model.sudo()
                if move.partner_id.l10n_ec_type_sri:
                    if move.type in ('in_invoice', 'in_refund'):
                        if move.partner_id.l10n_ec_type_sri == 'Ruc':
                            move.l10n_ec_identification_type_id = get_identification(
                                '01')
                        elif move.partner_id.l10n_ec_type_sri == 'Cedula':
                            move.l10n_ec_identification_type_id = get_identification(
                                '02')
                        elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                            move.l10n_ec_identification_type_id = get_identification(
                                '03')
                        else:
                            move.l10n_ec_identification_type_id = False
                    elif move.type in ('out_invoice', 'out_refund'):
                        if not move.l10n_ec_is_exportation:
                            if move.partner_id.l10n_ec_type_sri == 'Ruc':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '04')
                            elif move.partner_id.l10n_ec_type_sri == 'Cedula':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '05')
                            elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '06')
                            elif move.partner_id.l10n_ec_type_sri == 'Consumidor':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '07')
                            else:
                                move.l10n_ec_identification_type_id = False
                        else:
                            if move.partner_id.l10n_ec_type_sri == 'Ruc':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '20')
                            elif move.partner_id.l10n_ec_type_sri == 'Pasaporte':
                                move.l10n_ec_identification_type_id = get_identification(
                                    '21')
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
                            ('document_type_ids', 'in',
                             move.l10n_latam_document_type_id.ids)
                        ])
                else:
                    move.l10n_latam_available_document_type_ids = []
                if supports:
                    move.l10n_ec_tax_support_domain_ids = supports.ids
                else:
                    move.l10n_ec_tax_support_domain_ids = []
            else:
                move.l10n_latam_available_document_type_ids = []
                move.l10n_ec_tax_support_domain_ids = []

    l10n_ec_identification_type_id = fields.Many2one('l10n_ec.identification.type',
                                                     string="Ecuadorian Identification Type",
                                                     store=True, compute='_get_l10n_ec_identification_type',
                                                     compute_sudo=True)
    l10n_ec_tax_support_domain_ids = fields.Many2many(comodel_name="l10n_ec.tax.support",
                                                      string="Tax Support Domain",
                                                      compute='_get_l10n_ec_identification_type',
                                                      compute_sudo=True)
    # replace field from Abstract class for change attributes(readonly and states)
    l10n_ec_point_of_emission_id = fields.Many2one(comodel_name="l10n_ec.point.of.emission",
        readonly=True, states={'draft': [('readonly', False)]})
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
                                             required=False,
                                             default=False,
                                             readonly=True,
                                             states={'draft': [('readonly', False)]})

    @api.depends(
        'name',
        'l10n_latam_document_type_id',
    )
    def _compute_l10n_ec_document_number(self):
        recs_with_name = self.filtered(
            lambda x: x.name != '/' and x.company_id.country_id.code == 'EC')
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

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.partner_id and self.partner_id.l10n_ec_sri_payment_id:
            self.l10n_ec_sri_payment_id = self.partner_id.l10n_ec_sri_payment_id.id
        return res

    @api.model
    def default_get(self, fields):
        values = super(AccountMove, self).default_get(fields)
        type = values.get('type', self.type)
        if type in ('out_invoice', 'out_refund', 'in_invoice'):
            invoice_type = modules_mapping.get_invoice_type(type,
                                                            values.get(
                                                                'l10n_ec_debit_note', self.l10n_ec_debit_note),
                                                            values.get('l10n_ec_liquidation', self.l10n_ec_liquidation))
            if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out', 'liquidation', 'in_invoice'):
                default_printer = self.env['res.users']. \
                    get_default_point_of_emission(self.env.user.id, raise_exception=True).get(
                        'default_printer_default_id')
                values['l10n_ec_point_of_emission_id'] = default_printer.id
                if default_printer:
                    values['l10n_ec_type_emission'] = default_printer.type_emission
                    if invoice_type == 'in_invoice':
                        next_number, auth_line = default_printer.get_next_value_sequence(
                            'withhold_purchase', False, False)
                        if next_number:
                            values['l10n_ec_withhold_number'] = next_number
                        if auth_line:
                            values['l10n_ec_authorization_line_id'] = auth_line.id
                    else:
                        next_number, auth_line = default_printer.get_next_value_sequence(
                            invoice_type, False, False)
                        if next_number:
                            values['l10n_latam_document_number'] = next_number
                        if auth_line:
                            values['l10n_ec_authorization_line_id'] = auth_line.id
        return values

    def copy(self, default=None):
        if not default:
            default = {}
        if self.filtered(lambda x: x.company_id.country_id.code == 'EC'):
            invoice_type = modules_mapping.get_invoice_type(
                self.type, self.l10n_ec_debit_note, self.l10n_ec_liquidation)
            next_number, auth_line = self.l10n_ec_point_of_emission_id.get_next_value_sequence(
                invoice_type, False, False)
            default['l10n_latam_document_number'] = next_number
            default['l10n_ec_authorization_line_id'] = auth_line.id
        return super(AccountMove, self).copy(default)

    l10n_ec_withhold_number = fields.Char(
        string='Withhold Number',
        required=False,
        readonly=True,
        states={'draft': [('readonly', False)]})

    @api.onchange(
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
        'l10n_ec_point_of_emission_id',
        'invoice_date',
    )
    def _onchange_point_of_emission(self):
        for move in self.filtered(lambda x: x.company_id.country_id.code == 'EC' and x.type
                                  in ('out_invoice', 'out_refund', 'in_invoice')):
            if move.l10n_ec_point_of_emission_id:
                invoice_type = modules_mapping.get_invoice_type(move.type, move.l10n_ec_debit_note,
                                                                move.l10n_ec_liquidation)
                if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out', 'liquidation', 'in_invoice'):
                    if invoice_type == 'in_invoice':
                        next_number, auth_line = move.l10n_ec_point_of_emission_id.get_next_value_sequence(
                            'withhold_purchase', move.invoice_date, False)
                        if next_number:
                            move.l10n_ec_withhold_number = next_number
                        if auth_line:
                            move.l10n_ec_authorization_line_id = auth_line.id
                    else:
                        next_number, auth_line = move.l10n_ec_point_of_emission_id.get_next_value_sequence(
                            invoice_type, move.invoice_date, False)
                        if next_number:
                            move.l10n_latam_document_number = next_number
                        if auth_line:
                            move.l10n_ec_authorization_line_id = auth_line.id

    l10n_ec_withhold_required = fields.Boolean(
        string='Withhold Required',
        compute='_get_l10n_ec_withhold_required',
        store=True,
    )
    l10n_ec_withhold_date = fields.Date(
        string='Withhold Date',
        required=False)

    @api.depends(
        'type',
        'line_ids.tax_ids',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
    )
    def _get_l10n_ec_withhold_required(self):
        group_iva_withhold = self.env.ref('l10n_ec_niif.tax_group_iva_withhold')
        group_rent_withhold = self.env.ref(
            'l10n_ec_niif.tax_group_renta_withhold')
        for rec in self:
            withhold_required = False
            if rec.type == 'in_invoice':
                withhold_required = any(t.tax_group_id.id in (group_iva_withhold.id, group_rent_withhold.id)
                                        for t in rec.line_ids.mapped('tax_ids'))
            rec.l10n_ec_withhold_required = withhold_required

    @api.constrains(
        'name',
        'l10n_ec_document_number',
        'company_id',
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
    )
    def _check_l10n_ec_document_number_duplicity(self):
        auth_line_model = self.env['l10n_ec.sri.authorization.line']
        for move in self.filtered(lambda x: x.company_id.country_id.code == 'EC'
                                  and modules_mapping.get_invoice_type(x.type,
                                                                       x.l10n_ec_debit_note,
                                                                       x.l10n_ec_liquidation, False)
                                  in ('out_invoice', 'out_refund', 'debit_note_out', 'liquidation')
                                  and x.l10n_ec_document_number):
            auth_line_model.with_context(from_constrain=True).validate_unique_value_document(
                modules_mapping.get_invoice_type(
                    move.type, move.l10n_ec_debit_note, move.l10n_ec_liquidation),
                move.l10n_ec_document_number, move.company_id.id, move.id)

    @api.depends(
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
    )
    def _compute_l10n_ec_invoice_filter_type_domain(self):
        for move in self:
            if move.is_sale_document(include_receipts=True):
                if not move.l10n_ec_debit_note:
                    move.l10n_ec_invoice_filter_type_domain = 'sale'
                else:
                    move.l10n_ec_invoice_filter_type_domain = 'debit_note_out'
            elif move.is_purchase_document(include_receipts=True):
                if not move.l10n_ec_debit_note and not move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = 'purchase'
                elif move.l10n_ec_debit_note and not move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = 'debit_note_in'
                elif not move.l10n_ec_debit_note and move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = 'liquidation'
                else:
                    move.l10n_ec_invoice_filter_type_domain = 'purchase'
            else:
                move.l10n_ec_invoice_filter_type_domain = False

    l10n_ec_invoice_filter_type_domain = fields.Char(string="Journal Domain",
                                                     required=False,
                                                     compute='_compute_l10n_ec_invoice_filter_type_domain')

    @api.model
    def _get_default_journal(self):
        journal_model = self.env['account.journal']
        if self.env.context.get('default_type', False) in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
            invoice_type = modules_mapping.get_invoice_type(self.env.context.get('default_type', False),
                                                            self.env.context.get(
                                                                'default_l10n_ec_debit_note', False),
                                                            self.env.context.get('default_l10n_ec_liquidation', False))
            if invoice_type in ('debit_note_in', 'debit_note_out', 'liquidation'):
                journal = journal_model.search([
                    ('company_id', '=', self._context.get(
                        'default_company_id', self.env.company.id)),
                    ('l10n_ec_extended_type', '=', invoice_type),
                ])
                if journal:
                    return super(AccountMove, self.with_context(default_journal_id=journal.id))._get_default_journal()
        return super(AccountMove, self)._get_default_journal()

    journal_id = fields.Many2one(default=_get_default_journal)

    @api.onchange(
        'l10n_ec_original_invoice_id',
        'invoice_date',
    )
    def onchange_l10n_ec_original_invoice(self):
        line_model = self.env['account.move.line'].with_context(
            check_move_validity=False)
        if self.l10n_ec_original_invoice_id:
            lines = line_model.browse()
            default_move = {
                'ref': _('Reversal'),
                'date': self.invoice_date or fields.Date.context_today(self),
                'invoice_date': self.invoice_date or fields.Date.context_today(self),
                'journal_id': self.journal_id and self.journal_id.id,
                'invoice_payment_term_id': None,
            }
            move_vals = self.l10n_ec_original_invoice_id._reverse_move_vals(
                default_move)
            for a, b, line_data in move_vals.get('line_ids'):
                if line_data.get('exclude_from_invoice_tab', False):
                    continue
                if 'move_id' in line_data:
                    line_data.pop('move_id')
                if not 'date' in line_data:
                    line_data.update({
                        'date': self.invoice_date or fields.Date.context_today(self),
                    })
                new_line = line_model.new(line_data)
                if new_line.currency_id:
                    new_line._onchange_currency()
                lines += new_line
            self.line_ids = lines
            self._recompute_dynamic_lines(recompute_all_taxes=True)

    @api.depends(
        'commercial_partner_id'
    )
    def _get_l10n_ec_consumidor_final(self):
        consumidor_final = self.env.ref('l10n_ec_niif.consumidor_final')
        for move in self:
            if move.commercial_partner_id.id == consumidor_final.id:
                move.l10n_ec_consumidor_final = True
            else:
                move.l10n_ec_consumidor_final = False

    l10n_ec_consumidor_final = fields.Boolean(
        string="Consumidor Final", compute="_get_l10n_ec_consumidor_final")

    def action_post(self):
        for move in self:
            if move.company_id.country_id.code == 'EC':
                if move.l10n_ec_consumidor_final and move.type == 'out_invoice'\
                    and float_compare(move.amount_total, move.company_id.l10n_ec_consumidor_final_limit,
                                      precision_digits=2) == 1:
                    raise UserError(_("You can't make invoice where amount total %s "
                                      "is bigger than %s for final customer")
                                    % (move.amount_total, move.company_id.l10n_ec_consumidor_final_limit))
                if move.l10n_ec_consumidor_final and move.type == 'out_refund':
                    raise UserError(
                        _("You can't make refund to final customer on ecuadorian company"))
                if move.l10n_ec_consumidor_final and move.type in ('in_refund', 'in_invoice'):
                    raise UserError(
                        _("You can't make bill or refund to final customer on ecuadorian company"))
                if move.type == 'in_invoice':
                    withhold_model = self.env['l10n_ec.withhold']
                    withhold_line_model = self.env['l10n_ec.withhold.line']
                    tax_model = self.env['account.tax']
                    percent_model = self.env['l10n_ec.withhold.line.percent']
                    withhold_iva_group = self.env.ref(
                        'l10n_ec_niif.tax_group_iva_withhold')
                    withhold_rent_group = self.env.ref(
                        'l10n_ec_niif.tax_group_renta_withhold')
                    iva_group = self.env.ref('l10n_ec_niif.tax_group_iva')
                    errors = {}
                    for line in move.invoice_line_ids:
                        iva_taxes = line.tax_ids.filtered(
                            lambda x: x.tax_group_id.id == iva_group.id and x.amount > 0)
                        iva_0_taxes = line.tax_ids.filtered(
                            lambda x: x.tax_group_id.id == iva_group.id and x.amount == 0)
                        withhold_iva_taxes = line.tax_ids.filtered(lambda x: x.tax_group_id.id == withhold_iva_group.id
                                                                   and x.amount > 0)
                        rent_withhold_taxes = line.tax_ids.filtered(
                            lambda x: x.tax_group_id.id == withhold_rent_group.id)
                        errors.setdefault(line, [])
                        if move.partner_id.country_id.code == 'EC':
                            if len(rent_withhold_taxes) == 0:
                                errors[line].append(
                                    _('You must apply at least one income withholding tax'))
                            if len(iva_taxes) == 0 and len(iva_0_taxes) == 0:
                                errors[line].append(
                                    _('You must apply at least one VAT tax'))
                        if len(iva_taxes) >= 1 and len(iva_0_taxes) >= 1:
                            errors[line].append(
                                _('Cannot apply VAT zero rate with another VAT rate'))
                        if len(iva_taxes) > 1:
                            errors[line].append(_('You cannot have more than one VAT tax %s')
                                                % (' / '.join(t.description or t.name for t in iva_taxes)))
                        if len(iva_0_taxes) > 1:
                            errors[line].append(_('You cannot have more than one VAT 0 tax %s')
                                                % (' / '.join(t.description or t.name for t in iva_0_taxes)))
                        if len(withhold_iva_taxes) > 1:
                            errors[line].append(_('You cannot have more than one VAT Withholding tax %s')
                                                % (' / '.join(t.description or t.name for t in withhold_iva_taxes)))
                        if len(rent_withhold_taxes) > 1:
                            errors[line].append(_('You cannot have more than one Rent Withholding tax %s')
                                                % (' / '.join(t.description or t.name for t in rent_withhold_taxes)))
                        if len(iva_taxes) == 0 and len(withhold_iva_taxes) > 0:
                            errors[line].append(_('You cannot apply VAT withholding without an assigned VAT tax %s')
                                                % (' / '.join(t.description or t.name for t in withhold_iva_taxes)))
                    error_message = ''
                    for eline in errors.keys():
                        error_message += '\n'.join(errors[eline])
                    if error_message:
                        raise UserError(error_message)
                    if not move.l10n_ec_withhold_required:
                        return super(AccountMove, self).action_post()
                    current_withhold = withhold_model.create({
                        'company_id': move.company_id.id,
                        'number': move.l10n_ec_withhold_number,
                        'issue_date': move.l10n_ec_withhold_date,
                        'partner_id': move.partner_id.id,
                        'invoice_id': move.id,
                        'type': 'purchase',
                        'document_type': move.l10n_ec_type_emission,
                        'point_of_emission_id': move.l10n_ec_point_of_emission_id.id,
                        'authorization_line_id': move.l10n_ec_authorization_line_id.id,
                        'state': 'draft',
                    })
                    tax_data = {}
                    for line in move.invoice_line_ids:
                        for tax in line.tax_ids:
                            if tax.tax_group_id.id in (withhold_iva_group.id, withhold_rent_group.id):
                                base_tag_id = tax.invoice_repartition_line_ids.filtered(
                                    lambda x: x.repartition_type == 'base').mapped('tag_ids')
                                tax_tag_id = tax.invoice_repartition_line_ids.filtered(
                                    lambda x: x.repartition_type == 'tax').mapped('tag_ids')
                                tax_type = tax.tax_group_id.id == withhold_iva_group.id \
                                    and 'iva' or tax.tax_group_id.id == withhold_rent_group.id and 'rent'
                                percent = tax.tax_group_id.id == withhold_iva_group.id \
                                    and abs(tax.invoice_repartition_line_ids.filtered(
                                        lambda x: x.repartition_type == 'tax').factor_percent) or abs(tax.amount)
                                tax_data.setdefault(tax.id, {
                                    'withhold_id': current_withhold.id,
                                    'invoice_id': move.id,
                                    'tax_id': tax.id,
                                    'base_tag_id': base_tag_id and base_tag_id.ids[0] or False,
                                    'tax_tag_id': tax_tag_id and tax_tag_id.ids[0] or False,
                                    'type': tax_type,
                                    'base_amount': 0.0,
                                    'tax_amount': 0.0,
                                    'base_amount_currency': 0.0,
                                    'tax_amount_currency': 0.0,
                                    'percent_id': percent_model._get_percent(percent, tax_type).id,
                                })
                    for tax_id in tax_data.keys():
                        base_amount = 0
                        tax_amount = 0
                        base_tag_id = tax_data[tax_id].get('base_tag_id')
                        tax_tag_id = tax_data[tax_id].get('tax_tag_id')
                        for line in move.line_ids:
                            for tag in line.tag_ids.filtered(lambda x: x.id in (base_tag_id, tax_tag_id)):
                                tag_amount = line.balance
                                if tag.id == base_tag_id:
                                    base_amount = abs(tag_amount)
                                    tax_data[tax_id]['base_amount'] += base_amount
                                    tax_data[tax_id]['base_amount_currency'] += move.currency_id.compute(
                                        base_amount, move.company_id.currency_id)
                                if tag.id == tax_tag_id:
                                    tax_amount = abs(tag_amount)
                                    tax_data[tax_id]['tax_amount'] += tax_amount
                                    tax_data[tax_id]['tax_amount_currency'] += move.currency_id.compute(
                                        tax_amount, move.company_id.currency_id)
                    for tax_id in tax_data.keys():
                        current_tax = tax_model.browse(tax_id)
                        if current_tax.tax_group_id.id == withhold_iva_group.id:
                            tax_data[tax_id]['base_amount'] = (tax_data[tax_id]['tax_amount']
                                                               / (percent_model.browse(tax_data[tax_id]['percent_id']).percent / 100.0))
                            tax_data[tax_id]['base_amount_currency'] = move.currency_id.compute(
                                tax_data[tax_id]['base_amount'], move.company_id.currency_id)
                    for withhold_line in tax_data.values():
                        withhold_line_model.create(withhold_line)
                    current_withhold.action_done()
                # proceso de facturacion electronica
                if move.is_invoice():
                    move.generate_xml_data()
        return super(AccountMove, self).action_post()

    def unlink(self):
        if self.env.context.get('skip_recurtion', False):
            return super(AccountMove, self).unlink()
        for move in self:
            if move.company_id.country_id.code == 'EC':
                if move.type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                    if move.state != 'draft':
                        raise UserError(
                            _("You only delete invoices in draft state"))
                    else:
                        move.with_context(skip_recurtion=True,
                                          force_delete=True).unlink()

    @api.depends(
        'line_ids.price_subtotal',
        'line_ids.tax_base_amount',
        'line_ids.tax_line_id',
        'partner_id',
        'currency_id'
    )
    def _compute_l10n_ec_amounts(self):
        for move in self:
            move_date = move.date or fields.Date.context_today(move)
            l10n_ec_base_iva_0 = 0.0
            l10n_ec_base_iva = 0.0
            l10n_ec_iva = 0.0
            l10n_ec_discount_total = 0.0
            for line in move.invoice_line_ids:
                l10n_ec_discount_total += line._l10n_ec_get_discount_total()
            for group in move.amount_by_group:
                iva_group = self.env.ref('l10n_ec_niif.tax_group_iva')
                if group[6] == iva_group.id:
                    if group[2] != 0 and group[1] == 0:
                        l10n_ec_base_iva_0 = group[2]
                    else:
                        l10n_ec_base_iva = group[2]
                        l10n_ec_iva = group[1]
            move.l10n_ec_base_iva_0 = l10n_ec_base_iva_0
            move.l10n_ec_base_iva = l10n_ec_base_iva
            move.l10n_ec_iva = l10n_ec_iva
            move.l10n_ec_discount_total = l10n_ec_discount_total
            move.l10n_ec_base_iva_0_currency = move.currency_id._convert(
                l10n_ec_base_iva_0, move.company_currency_id, move.company_id, move_date)
            move.l10n_ec_base_iva_currency = move.currency_id._convert(
                l10n_ec_base_iva, move.company_currency_id, move.company_id, move_date)
            move.l10n_ec_iva_currency = move.currency_id._convert(
                l10n_ec_iva, move.company_currency_id, move.company_id, move_date)
            move.l10n_ec_discount_total_currency = move.currency_id._convert(
                l10n_ec_discount_total, move.company_currency_id, move.company_id, move_date)

    l10n_ec_withhold_id = fields.Many2one(
        comodel_name="l10n_ec.withhold",
        string="Withhold",
        required=False)

    l10n_ec_withhold_line_ids = fields.One2many(
        comodel_name='l10n_ec.withhold.line',
        inverse_name='invoice_id',
        string='Withhold Lines',
        required=False)

    l10n_ec_withhold_ids = fields.Many2many(
        comodel_name='l10n_ec.withhold',
        string='Withhold',
        compute='_get_l10n_ec_withhold_ids',
    )
    l10n_ec_withhold_count = fields.Integer(
        string='Withhold Count',
        compute='_get_l10n_ec_withhold_ids',
        store=False
    )

    @api.depends(
        'l10n_ec_withhold_line_ids.withhold_id',
    )
    def _get_l10n_ec_withhold_ids(self):
        for rec in self:
            l10n_ec_withhold_ids = rec.l10n_ec_withhold_line_ids.mapped(
                'withhold_id').ids
            if not l10n_ec_withhold_ids:
                l10n_ec_withhold_ids = rec.l10n_ec_withhold_ids.search(
                    [('invoice_id', '=', rec.id)]).ids
            rec.l10n_ec_withhold_ids = l10n_ec_withhold_ids
            rec.l10n_ec_withhold_count = len(l10n_ec_withhold_ids)

    def action_show_l10n_ec_withholds(self):
        self.ensure_one()
        type = self.mapped('type')[0]
        action = self.env.ref(
            'l10n_ec_niif.l10n_ec_withhold_purchase_act_window').read()[0]

        withholds = self.mapped('l10n_ec_withhold_ids')
        if len(withholds) > 1:
            action['domain'] = [('id', 'in', withholds.ids)]
        elif withholds:
            form_view = [
                (self.env.ref('l10n_ec_niif.l10n_ec_withhold_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = withholds.id
        action['context'] = dict(self._context,
                                 default_partner_id=self.partner_id.id,
                                 default_invoice_id=self.id)
        return action

    def create_withhold_customer(self):
        self.ensure_one()
        action = self.env.ref(
            'l10n_ec_niif.l10n_ec_withhold_sales_act_window').read()[0]
        action['views'] = [
            (self.env.ref('l10n_ec_niif.l10n_ec_withhold_form_view').id, 'form')]
        ctx = eval(action['context'])
        ctx.update({
            'default_partner_id': self.partner_id.id,
            'default_invoice_id': self.id,
            'default_type': 'sale',
            'default_issue_date': self.invoice_date,
            'default_document_type': self.l10n_ec_type_emission,
            'default_l10n_ec_is_create_from_invoice': True,
        })
        action['context'] = ctx
        return action

    l10n_ec_start_date = fields.Date(
        'Start Date', related='l10n_ec_authorization_id.start_date')
    l10n_ec_expiration_date = fields.Date(
        'Expiration Date', related='l10n_ec_authorization_id.expiration_date')

    @api.constrains('l10n_ec_start_date', 'l10n_ec_expiration_date', 'invoice_date')
    def _check_outside(self):
        if any(outside_start for outside_start in self
               if outside_start.invoice_date and outside_start.l10n_ec_start_date
               and outside_start.invoice_date < outside_start.l10n_ec_start_date):
            raise UserError(_('Invoice date outside defined date range'))
        if any(outside_expiration for outside_expiration in self
               if outside_expiration.invoice_date and outside_expiration.l10n_ec_expiration_date
               and outside_expiration.invoice_date > outside_expiration.l10n_ec_expiration_date):
            raise UserError(_('Invoice date outside defined date range2'))

    @api.model
    def get_invoice_type(self, invoice_type, debit_note=False, liquidation=False):
        return modules_mapping.get_invoice_type(invoice_type, debit_note, liquidation)

    def generate_xml_data(self):
        xml_model = self.env['sri.xml.data']
        xml_recs = self.env['sri.xml.data'].browse()
        #si por context me pasan que no cree la parte electronica
        if self.env.context.get('no_create_electronic', False):
            return True
        l10n_ec_type_conection_sri = self.env.company.l10n_ec_type_conection_sri
        #Si ya se encuentra autorizado, no hacer nuevamente el proceso de generacion del xml
        for invoice in self.filtered(lambda x: not x.ln10_ec_xml_data_id):
            invoice_type = invoice.get_invoice_type(invoice.type,
                                                    invoice.l10n_ec_debit_note,
                                                    invoice.l10n_ec_liquidation)
            if invoice.type == 'in_invoice':
                for retention in invoice.l10n_ec_withhold_ids:
                    if retention.point_of_emission_id.type_emission != 'electronic':
                        continue
                    if not retention.no_number:
                        #si el documento esta habilitado, hacer el proceso electronico
                        if xml_model._is_document_authorized('withhold_purchase'):
                            sri_xml_vals = retention._prepare_l10n_ec_sri_xml_values(l10n_ec_type_conection_sri)
                            sri_xml_vals['withhold_id'] = retention.id
                            new_xml_rec = xml_model.create(sri_xml_vals)
                            xml_recs += new_xml_rec
            # si el documento esta habilitado, hacer el proceso electronico
            elif invoice.l10n_ec_point_of_emission_id.type_emission == 'electronic' and \
                    xml_model._is_document_authorized(invoice_type):
                if not invoice.partner_id.street:
                    raise UserError(
                        f"Debe asignar la direccion en el cliente {invoice.partner_id.name}, por favor verifique")
                # if not invoice.l10n_ec_sri_payment_id:
                #     raise UserError(
                #         f"Debe asignar la forma de pago del SRI en la factura: {invoice.document_number}, por favor verifique")
                sri_xml_vals = invoice._prepare_l10n_ec_sri_xml_values(l10n_ec_type_conection_sri)
                #factura
                if invoice_type == 'out_invoice':
                    sri_xml_vals['invoice_out_id'] = invoice.id
                # nota de debito
                elif invoice_type == 'debit_note_out':
                    sri_xml_vals['debit_note_out_id'] = invoice.id
                #nota de credito
                elif invoice_type == 'out_refund':
                    # if not invoice.refund_invoice_id and not invoice.numero_documento:
                    #     raise UserError(
                    #         "La Nota de Credito: %s no esta asociada a ningun documento que modifique tributariamente, por favor verifique" % invoice.document_number)
                    # # validar que la factura este autorizada electronicamente
                    # if invoice.refund_invoice_id and not invoice.refund_invoice_id.ln10_ec_xml_data_id:
                    #     raise UserError(
                    #         "No puede generar una Nota de credito, cuya factura rectificativa no esta autorizada electronicamente!")
                    sri_xml_vals['credit_note_out_id'] = invoice.id
                # liquidacion de compas
                elif invoice_type == 'liquidation':
                    sri_xml_vals['liquidation_id'] = invoice.id
                new_xml_rec = xml_model.create(sri_xml_vals)
                xml_recs += new_xml_rec
        if xml_recs:
            send_file = True
            #en modo offline no enviar el documento inmeditamente
            #pasarlo a cola para q se envie por debajo
            if l10n_ec_type_conection_sri == 'offline':
                send_file = False
            xml_recs.process_document_electronic(send_file)
        return True

    @api.model
    def get_total_impuestos(self, parent_node, codigo, codigo_porcentaje, base, valor, tag_name='totalImpuesto',
                            tarifa=-1, reembolso=False, liquidation=False, decimales=2):
        util_model = self.env['l10n_ec.utils']
        tag = SubElement(parent_node, tag_name)
        SubElement(tag, "codigo").text = codigo
        SubElement(tag, "codigoPorcentaje").text = codigo_porcentaje
        if liquidation:
            if reembolso:
                SubElement(tag, "baseImponibleReembolso").text = util_model.formato_numero(base, decimales)
                if tarifa != -1:
                    SubElement(tag, "tarifa").text = util_model.formato_numero(tarifa, 0)
                SubElement(tag, "valorReembolso").text = util_model.formato_numero(valor, decimales)
            else:
                SubElement(tag, "baseImponible").text = util_model.formato_numero(base, decimales)
                if tarifa != -1:
                    SubElement(tag, "tarifa").text = util_model.formato_numero(tarifa, 0)
                SubElement(tag, "valor").text = util_model.formato_numero(valor, decimales)
        else:
            if tarifa != -1:
                SubElement(tag, "tarifa").text = util_model.formato_numero(tarifa, 0)
            if reembolso:
                SubElement(tag, "baseImponibleReembolso").text = util_model.formato_numero(base, decimales)
                SubElement(tag, "valorReembolso").text = util_model.formato_numero(valor, decimales)
            else:
                SubElement(tag, "baseImponible").text = util_model.formato_numero(base, decimales)
                SubElement(tag, "valor").text = util_model.formato_numero(valor, decimales)
        return tag

    @api.model
    def get_motives(self, parent_node, razon="", valor=0, tag_name="motivo"):
        util_model = self.env['l10n_ec.utils']
        tag = SubElement(parent_node, tag_name)
        SubElement(tag, "razon").text = razon
        SubElement(tag, "valor").text = util_model.formato_numero(valor, 2)
        return tag

    @api.model
    def add_info_adicional(self, parent_node, dict_data=None):
        # Hacer una funcion que me permita agregar los campos adicionales que deben ser pasados en un diccionario
        return True

    def get_pagos_data(self):
        # TODO: agregar informacion de pagos, considerar para ATS
        return []

    @api.model
    def get_info_factura(self, invoice_id, node):
        util_model = self.env['l10n_ec.utils']
        xml_model = self.env['sri.xml.data']
        company = self.env.company
        currency = company.currency_id
        precision_get = self.env['decimal.precision'].precision_get
        digits_precision_product = precision_get('Product Price')
        digits_precision_qty = precision_get('Product Unit of Measure')
        digits_precision_discount = precision_get('Discount')
        invoice = self.browse(invoice_id)
        infoFactura = SubElement(node, "infoFactura")
        fecha_factura = invoice.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoFactura, "fechaEmision").text = fecha_factura
        address = company.partner_id.street
        SubElement(infoFactura, "dirEstablecimiento").text = util_model._clean_str(address)[:300]
        if invoice.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = invoice.l10n_ec_identification_type_id.code
        elif invoice.commercial_partner_id:
            # si no hay l10n_ec_identification_type_id, se debe pasar un valor segun tabla 7 de la ficha tecnica del sri, no 00
            # buscar el tipo de identificacion del cliente, si es cedula, ruc
            if invoice.commercial_partner_id.type_ref == 'ruc':
                tipoIdentificacionComprador = '04'
            elif invoice.commercial_partner_id.type_ref == 'cedula':
                tipoIdentificacionComprador = '05'
            elif invoice.commercial_partner_id.type_ref == 'passport':
                tipoIdentificacionComprador = '06'
            else:
                # pasar por defecto consumidor final
                tipoIdentificacionComprador = '07'
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = '07'
        numero_contribuyente_especial = company.get_contribuyente_data(invoice.invoice_date)
        SubElement(infoFactura, "contribuyenteEspecial").text = numero_contribuyente_especial
        SubElement(infoFactura, "obligadoContabilidad").text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id)
        SubElement(infoFactura, "tipoIdentificacionComprador").text = tipoIdentificacionComprador
        # if invoice.remision_id:
        #     SubElement(infoFactura, "guiaRemision").text = invoice.remision_id.document_number
        SubElement(infoFactura, "razonSocialComprador").text = util_model._clean_str(
            invoice.commercial_partner_id.name[:300])
        SubElement(infoFactura, "identificacionComprador").text = invoice.commercial_partner_id.vat
        SubElement(infoFactura, "direccionComprador").text = util_model._clean_str(invoice.commercial_partner_id.street)[:300]

        SubElement(infoFactura, "totalSinImpuestos").text = util_model.formato_numero(
            invoice.amount_untaxed, currency.decimal_places)
        # SubElement(infoFactura, "totalDescuento").text = util_model.formato_numero(
        #     invoice.total_descuento, currency.decimal_places)
        # Definicion de Impuestos
        totalConImpuestos = SubElement(infoFactura, "totalConImpuestos")
        if invoice.l10n_ec_base_iva_0 != 0:
            self.get_total_impuestos(totalConImpuestos, '2', '0', invoice.l10n_ec_base_iva_0, 0.0,
                                     decimales=currency.decimal_places)
        if invoice.l10n_ec_base_iva != 0:
            self.get_total_impuestos(totalConImpuestos, '2', '2', invoice.l10n_ec_base_iva, invoice.l10n_ec_iva,
                                     decimales=currency.decimal_places)
        # if invoice.base_no_iva != 0:
        #     self.get_total_impuestos(totalConImpuestos, '2', '6', invoice.base_no_iva, 0.0,
        #                              decimales=currency.decimal_places)
        # SubElement(infoFactura, "propina").text = util_model.formato_numero(invoice.propina or 0,
        #                                                                         currency.decimal_places)
        SubElement(infoFactura, "importeTotal").text = util_model.formato_numero(invoice.amount_total,
                                                                                     currency.decimal_places)
        SubElement(infoFactura, "moneda").text = invoice.company_id.currency_id.name or 'DOLAR'
        # Procesamiento de los pagos
        pagos_data = invoice.get_pagos_data()
        if pagos_data:
            pagos = SubElement(infoFactura, "pagos")
            for payment_code in pagos_data.keys():
                pago = SubElement(pagos, "pago")
                SubElement(pago, "formaPago").text = payment_code
                SubElement(pago, "total").text = util_model.formato_numero(pagos_data.get(payment_code, 0.0))
        else:
            if not company.l10n_ec_sri_payment_id:
                raise UserError(_(
                    u'Debe configurar la forma de pago por defecto esto lo encuentra en Contabilidad / SRI / Configuración'))
            pagos = SubElement(infoFactura, "pagos")
            pago = SubElement(pagos, "pago")
            payment_code = company.l10n_ec_sri_payment_id.code
            if invoice.l10n_ec_sri_payment_id:
                payment_code = invoice.l10n_ec_sri_payment_id.code
            elif invoice.commercial_partner_id.l10n_ec_sri_payment_id:
                payment_code = invoice.commercial_partner_id.l10n_ec_sri_payment_id.code
            SubElement(pago, "formaPago").text = payment_code
            SubElement(pago, "total").text = util_model.formato_numero(invoice.amount_total)
            if invoice.invoice_payment_term_id:
                if invoice.invoice_payment_term_id.sri_type == 'credito':
                    if invoice.dias_credito > 0:
                        SubElement(pago, "plazo").text = util_model.formato_numero(invoice.dias_credito, 0)
                        SubElement(pago, "unidadTiempo").text = 'dias'
        # Lineas de Factura
        detalles = SubElement(node, "detalles")
        for line in invoice.invoice_line_ids.filtered(lambda x: not x.display_type):
            discount = round(((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2)
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            if currency.is_zero(subtotal):
                continue
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoPrincipal").text = util_model._clean_str(
                line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            #             SubElement(detalle,"codigoAdicional").text = util_model._clean_str(line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300])
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(line.quantity, digits_precision_qty)
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(line.price_unit,
                                                                                   digits_precision_product)
            SubElement(detalle, "descuento").text = util_model.formato_numero(discount or 0.0,
                                                                              digits_precision_discount)
            SubElement(detalle, "precioTotalSinImpuesto").text = util_model.formato_numero(subtotal,
                                                                                           currency.decimal_places)
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.get_total_impuestos(impuestos, '2', '0', line.l10n_ec_base_iva_0, 0.0, 'impuesto', 0,
                                         decimales=currency.decimal_places)
            if line.l10n_ec_base_iva != 0:
                self.get_total_impuestos(impuestos, '2', '2', line.l10n_ec_base_iva, line.l10n_ec_iva, 'impuesto', 12,
                                         decimales=currency.decimal_places)
            # if line.base_no_iva != 0:
            #     self.get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0,
            #                              decimales=currency.decimal_places)
        # Las retenciones solo aplican para el esquema de gasolineras
        # retenciones = SubElement(node,"retenciones")
        infoAdicional = SubElement(node, "infoAdicional")
        campoAdicional = SubElement(infoAdicional, "campoAdicional")
        campoAdicional.set("nombre", "OtroCampo")
        campoAdicional.text = "Otra Informacion"
        return node

    @api.model
    def get_info_credit_note(self, credit_note_id, node):
        util_model = self.env['l10n_ec.utils']
        xml_model = self.env['sri.xml.data']
        company = self.env.company
        currency = company.currency_id
        precision_get = self.env['decimal.precision'].precision_get
        digits_precision_product = precision_get('Product Price')
        digits_precision_qty = precision_get('Product Unit of Measure')
        digits_precision_discount = precision_get('Discount')
        credit_note = self.browse(credit_note_id)
        infoNotaCredito = SubElement(node, "infoNotaCredito")
        fecha_factura = credit_note.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoNotaCredito, "fechaEmision").text = fecha_factura
        address = credit_note.partner_id.street
        SubElement(infoNotaCredito, "dirEstablecimiento").text = util_model._clean_str(address and address[:300] or '')
        if credit_note.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = credit_note.l10n_ec_identification_type_id.code
        elif credit_note.commercial_partner_id:
            # si no hay l10n_ec_identification_type_id, se debe pasar un valor segun tabla 7 de la ficha tecnica del sri, no 00
            # buscar el tipo de identificacion del cliente, si es cedula, ruc
            if credit_note.commercial_partner_id.type_ref == 'ruc':
                tipoIdentificacionComprador = '04'
            elif credit_note.commercial_partner_id.type_ref == 'cedula':
                tipoIdentificacionComprador = '05'
            elif credit_note.commercial_partner_id.type_ref == 'passport':
                tipoIdentificacionComprador = '06'
            else:
                # pasar por defecto consumidor final
                tipoIdentificacionComprador = '07'
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = '07'
        SubElement(infoNotaCredito, "tipoIdentificacionComprador").text = tipoIdentificacionComprador
        SubElement(infoNotaCredito, "razonSocialComprador").text = util_model._clean_str(
            credit_note.commercial_partner_id.name[:300])
        SubElement(infoNotaCredito, "identificacionComprador").text = credit_note.commercial_partner_id.vat
        company = self.env.user.company_id
        numero_contribuyente_especial = company.get_contribuyente_data(credit_note.invoice_date)
        SubElement(infoNotaCredito, "contribuyenteEspecial").text = numero_contribuyente_especial
        SubElement(infoNotaCredito, "obligadoContabilidad").text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id)
        if credit_note.rise:
            SubElement(infoNotaCredito, "rise").text = credit_note.rise
        # TODO: notas de credito solo se emitiran a facturas o a otros documentos???
        SubElement(infoNotaCredito, "codDocModificado").text = '01'
        SubElement(infoNotaCredito,
                   "numDocModificado").text = credit_note.numero_documento or credit_note.legacy_document_number or credit_note.invoice_rectification_id.document_number
        SubElement(infoNotaCredito, "fechaEmisionDocSustento").text = (credit_note.fecha_documento or credit_note.legacy_document_date or credit_note.invoice_rectification_id.invoice_date).strftime(util_model.get_formato_date())
        SubElement(infoNotaCredito, "totalSinImpuestos").text = util_model.formato_numero(
            credit_note.amount_untaxed, currency.decimal_places)
        SubElement(infoNotaCredito, "valorModificacion").text = util_model.formato_numero(credit_note.amount_total,
                                                                                              currency.decimal_places)
        SubElement(infoNotaCredito, "moneda").text = credit_note.company_id.currency_id.name or 'DOLAR'
        # Definicion de Impuestos
        totalConImpuestos = SubElement(infoNotaCredito, "totalConImpuestos")
        if credit_note.l10n_ec_base_iva_0 != 0:
            self.get_total_impuestos(totalConImpuestos, '2', '0', credit_note.l10n_ec_base_iva_0, 0.0,
                                     decimales=currency.decimal_places)
        if credit_note.l10n_ec_base_iva != 0:
            self.get_total_impuestos(totalConImpuestos, '2', '2', credit_note.l10n_ec_base_iva, credit_note.l10n_ec_iva,
                                     decimales=currency.decimal_places)
        # if credit_note.base_no_iva != 0:
        #     self.get_total_impuestos(totalConImpuestos, '2', '6', credit_note.base_no_iva, 0.0,
        #                              decimales=currency.decimal_places)
        SubElement(infoNotaCredito, "motivo").text = util_model._clean_str(
            credit_note.name and credit_note.name[:300] or 'NOTA DE CREDITO')
        # Lineas de Factura
        detalles = SubElement(node, "detalles")
        for line in credit_note.invoice_line_ids.filtered(lambda x: not x.display_type):
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoInterno").text = util_model._clean_str(
                line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            #             SubElement(detalle,"codigoAdicional").text = util_model._clean_str(line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300])
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(line.quantity, digits_precision_qty)
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(line.price_unit,
                                                                                       digits_precision_product)
            discount = round(((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2)
            # TODO: hacer un redondeo con las utilidades del sistema
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            SubElement(detalle, "descuento").text = util_model.formato_numero(discount or 0.0,
                                                                                  digits_precision_discount)
            SubElement(detalle, "precioTotalSinImpuesto").text = util_model.formato_numero(subtotal,
                                                                                               currency.decimal_places)
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.get_total_impuestos(impuestos, '2', '0', line.l10n_ec_base_iva_0, 0.0, 'impuesto', 0,
                                         decimales=currency.decimal_places)
            if line.l10n_ec_base_iva != 0:
                self.get_total_impuestos(impuestos, '2', '2', line.l10n_ec_base_iva, line.l10n_ec_iva, 'impuesto', 12,
                                         decimales=currency.decimal_places)
            # if line.base_no_iva != 0:
            #     self.get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0,
            #                              decimales=currency.decimal_places)
        infoAdicional = SubElement(node, "infoAdicional")
        campoAdicional = SubElement(infoAdicional, "campoAdicional")
        campoAdicional.set("nombre", "OtroCampo")
        campoAdicional.text = "Otra Informacion"
        return node

    @api.model
    def get_info_debit_note(self, debit_id, node):
        util_model = self.env['l10n_ec.utils']
        xml_model = self.env['sri.xml.data']
        company = self.env.company
        currency = company.currency_id
        debit = self.browse(debit_id)
        infoNotaDebito = SubElement(node, "infoNotaDebito")
        fecha_emision = debit.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoNotaDebito, "fechaEmision").text = fecha_emision
        address = debit.partner_id.street
        SubElement(infoNotaDebito, "dirEstablecimiento").text = util_model._clean_str(address and address[:300] or '')
        if debit.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = debit.l10n_ec_identification_type_id.code
        elif debit.commercial_partner_id:
            # si no hay l10n_ec_identification_type_id, se debe pasar un valor segun tabla 7 de la ficha tecnica del sri, no 00
            # buscar el tipo de identificacion del cliente, si es cedula, ruc
            if debit.commercial_partner_id.type_ref == 'ruc':
                tipoIdentificacionComprador = '04'
            elif debit.commercial_partner_id.type_ref == 'cedula':
                tipoIdentificacionComprador = '05'
            elif debit.commercial_partner_id.type_ref == 'passport':
                tipoIdentificacionComprador = '06'
            else:
                # pasar por defecto consumidor final
                tipoIdentificacionComprador = '07'
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = '07'
        SubElement(infoNotaDebito, "tipoIdentificacionComprador").text = tipoIdentificacionComprador
        SubElement(infoNotaDebito, "razonSocialComprador").text = util_model._clean_str(
            debit.commercial_partner_id.name[:300])
        SubElement(infoNotaDebito, "identificacionComprador").text = debit.commercial_partner_id.vat
        company = self.env.user.company_id
        numero_contribuyente_especial = company.get_contribuyente_data(debit.invoice_date)
        SubElement(infoNotaDebito, "contribuyenteEspecial").text = numero_contribuyente_especial
        SubElement(infoNotaDebito, "obligadoContabilidad").text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id)
        if debit.rise:
            SubElement(infoNotaDebito, "rise").text = debit.rise
        # TODO: notas de debito solo se emitiran a facturas o a otros documentos???
        SubElement(infoNotaDebito, "codDocModificado").text = '01'
        SubElement(infoNotaDebito,
                   "numDocModificado").text = debit.numero_documento or debit.legacy_document_number or debit.invoice_rectification_id.document_number
        SubElement(infoNotaDebito, "fechaEmisionDocSustento").text = (debit.fecha_documento or debit.legacy_document_date or debit.invoice_rectification_id.invoice_date).strftime(util_model.get_formato_date())
        SubElement(infoNotaDebito, "totalSinImpuestos").text = util_model.formato_numero(debit.amount_untaxed)
        # Definicion de Impuestos
        # xq no itero sobre los impuestos???'
        impuestos = SubElement(infoNotaDebito, "impuestos")
        if debit.l10n_ec_base_iva_0 != 0:
            self.get_total_impuestos(impuestos, '2', '0', debit.l10n_ec_base_iva_0, 0.0, 'impuesto', 0,
                                     decimales=currency.decimal_places)
        if debit.l10n_ec_base_iva != 0:
            # TODO: no se debe asumir que el % del iva es 12, tomar del impuesto directamente
            self.get_total_impuestos(impuestos, '2', '2', debit.l10n_ec_base_iva, debit.l10n_ec_iva, 'impuesto', 12,
                                     decimales=currency.decimal_places)
        # if debit.base_no_iva != 0:
        #     self.get_total_impuestos(impuestos, '2', '6', debit.base_no_iva, 0.0, 'impuesto', 0,
        #                              decimales=currency.decimal_places)
        SubElement(infoNotaDebito, "valorTotal").text = util_model.formato_numero(debit.amount_total,
                                                                                      currency.decimal_places)
        motivos = SubElement(node, "motivos")
        for line in debit.invoice_line_ids.filtered(lambda x: not x.display_type):
            self.get_motives(motivos,
                             util_model._clean_str(line.product_id and line.product_id.name[:300] or line.name[:300]),
                             line.price_subtotal)
        infoAdicional = SubElement(node, "infoAdicional")
        # TODO: agregar infoAdicional
        campoAdicional = SubElement(infoAdicional, "campoAdicional")
        campoAdicional.set("nombre", "OtroCampo")
        campoAdicional.text = "Otra Informacion"
        return node

    @api.model
    def get_info_liquidation(self, liquidation_id, node):
        util_model = self.env['l10n_ec.utils']
        xml_model = self.env['sri.xml.data']
        company = self.env.user.company_id
        liquidation = self.browse(liquidation_id)
        infoLiquidacionCompra = SubElement(node, "infoLiquidacionCompra")
        fecha_emision = liquidation.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoLiquidacionCompra, "fechaEmision").text = fecha_emision
        address = liquidation.partner_id.street
        SubElement(infoLiquidacionCompra, "dirEstablecimiento").text = util_model._clean_str(
            address and address[:300] or '')
        numero_contribuyente_especial = company.get_contribuyente_data(liquidation.invoice_date)
        SubElement(infoLiquidacionCompra, "contribuyenteEspecial").text = numero_contribuyente_especial
        SubElement(infoLiquidacionCompra, "obligadoContabilidad").text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id)
        if liquidation.commercial_partner_id:
            # si no hay l10n_ec_identification_type_id, se debe pasar un valor segun tabla 7 de la ficha tecnica del sri, no 00
            # buscar el tipo de identificacion del cliente, si es cedula, ruc
            if liquidation.commercial_partner_id.type_ref == 'ruc':
                tipoIdentificacionComprador = '04'
            elif liquidation.commercial_partner_id.type_ref == 'cedula':
                tipoIdentificacionComprador = '05'
            elif liquidation.commercial_partner_id.type_ref == 'passport':
                tipoIdentificacionComprador = '06'
            else:
                # pasar por defecto consumidor final
                tipoIdentificacionComprador = '07'
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = '07'
        SubElement(infoLiquidacionCompra, "tipoIdentificacionProveedor").text = tipoIdentificacionComprador
        SubElement(infoLiquidacionCompra, "razonSocialProveedor").text = util_model._clean_str(
            liquidation.commercial_partner_id.name[:300])
        SubElement(infoLiquidacionCompra, "identificacionProveedor").text = liquidation.commercial_partner_id.vat
        SubElement(infoLiquidacionCompra, "direccionProveedor").text = util_model._clean_str(
            liquidation.partner_id.street[:300])
        SubElement(infoLiquidacionCompra, "totalSinImpuestos").text = util_model.formato_numero(
            liquidation.amount_untaxed)
        # SubElement(infoLiquidacionCompra, "totalDescuento").text = util_model.formato_numero(
        #     liquidation.total_descuento)
        if liquidation.voucher_type_id and liquidation.voucher_type_id.code == '41':
            SubElement(infoLiquidacionCompra, "codDocReembolso").text = liquidation.voucher_type_id.code
            SubElement(infoLiquidacionCompra, "totalComprobantesReembolso").text = util_model.formato_numero(
                sum([r.total_invoice for r in liquidation.reembolso_ids]))
            SubElement(infoLiquidacionCompra, "totalBaseImponibleReembolso").text = util_model.formato_numero(
                sum([r.total_base_iva for r in liquidation.reembolso_ids]))
            SubElement(infoLiquidacionCompra, "totalImpuestoReembolso").text = util_model.formato_numero(
                sum([r.l10n_ec_iva for r in liquidation.reembolso_ids]) + sum(
                    [r.total_ice for r in liquidation.reembolso_ids]))
        # Definicion de Impuestos
        # xq no itero sobre los impuestos???'
        impuestos = SubElement(infoLiquidacionCompra, "totalConImpuestos")
        if liquidation.l10n_ec_base_iva_0 != 0:
            self.get_total_impuestos(impuestos, '2', '0', liquidation.l10n_ec_base_iva_0, 0.0, 'totalImpuesto', 0, False, True)
        if liquidation.l10n_ec_base_iva != 0:
            # TODO: no se debe asumir que el % del iva es 12, tomar del impuesto directamente
            self.get_total_impuestos(impuestos, '2', '2', liquidation.l10n_ec_base_iva, liquidation.l10n_ec_iva, 'totalImpuesto',
                                     12, False, True)
        # if liquidation.base_no_iva != 0:
        #     self.get_total_impuestos(impuestos, '2', '6', liquidation.base_no_iva, 0.0, 'totalImpuesto', 0, False, True)
        SubElement(infoLiquidacionCompra, "importeTotal").text = util_model.formato_numero(
            liquidation.amount_total)
        SubElement(infoLiquidacionCompra, "moneda").text = liquidation.company_id.currency_id.name
        pagos_data = liquidation.get_pagos_data()
        pagos = SubElement(infoLiquidacionCompra, "pagos")
        if pagos_data:
            for payment_code in pagos_data.keys():
                pago = SubElement(pagos, "pago")
                SubElement(pago, "formaPago").text = payment_code
                SubElement(pago, "total").text = util_model.formato_numero(pagos_data.get(payment_code, 0.0))
        else:
            if not company.l10n_ec_sri_payment_id:
                raise UserError(_(
                    u'Debe configurar la forma de pago por defecto esto lo encuentra en Contabilidad / SRI / Configuración'))
            pago = SubElement(pagos, "pago")
            payment_code = company.l10n_ec_sri_payment_id.code
            if liquidation.l10n_ec_sri_payment_id:
                payment_code = liquidation.l10n_ec_sri_payment_id.code
            elif liquidation.commercial_partner_id.l10n_ec_sri_payment_id:
                payment_code = liquidation.commercial_partner_id.l10n_ec_sri_payment_id.code
            SubElement(pago, "formaPago").text = payment_code
            SubElement(pago, "total").text = util_model.formato_numero(liquidation.amount_total)
            if liquidation.invoice_payment_term_id:
                if liquidation.invoice_payment_term_id.sri_type == 'credito':
                    if liquidation.dias_credito > 0:
                        SubElement(pago, "plazo").text = util_model.formato_numero(liquidation.dias_credito, 0)
                        SubElement(pago, "unidadTiempo").text = 'dias'
        detalles = SubElement(node, "detalles")
        for line in liquidation.invoice_line_ids:
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoPrincipal").text = util_model._clean_str(
                line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300])
            SubElement(detalle, "unidadMedida").text = line.uom_id and line.uom_id.display_name or 'N/A'
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(line.quantity, 6)
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(line.price_unit, 6)
            discount = round(((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2)
            # TODO: hacer un redondeo con las utilidades del sistema
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            SubElement(detalle, "descuento").text = util_model.formato_numero(discount or 0.0, 2)
            SubElement(detalle, "precioTotalSinImpuesto").text = util_model.formato_numero(subtotal, 2)
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.get_total_impuestos(impuestos, '2', '0', line.l10n_ec_base_iva_0, 0.0, 'impuesto', 0, False)
            if line.l10n_ec_base_iva != 0:
                self.get_total_impuestos(impuestos, '2', '2', line.l10n_ec_base_iva, line.l10n_ec_iva, 'impuesto',
                                         12, False)
            # if line.base_no_iva != 0:
            #     self.get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0, False)
        if liquidation.reembolso_ids:
            reembolsos = SubElement(node, "reembolsos")
            for reembolso in liquidation.reembolso_ids:
                tipoIdentificacionComprador = '07'
                # buscar el tipo de identificacion del cliente, si es cedula, ruc
                if reembolso.partner_id.commecial_partner_id.type_ref == 'ruc':
                    tipoIdentificacionComprador = '04'
                elif reembolso.partner_id.commecial_partner_id.type_ref == 'cedula':
                    tipoIdentificacionComprador = '05'
                elif reembolso.partner_id.commecial_partner_id.type_ref == 'passport':
                    tipoIdentificacionComprador = '06'
                SubElement(reembolsos, "tipoIdentificacionProveedorReembolso").text = tipoIdentificacionComprador
                SubElement(reembolsos,
                           "identificacionProveedorReembolso").text = reembolso.partner_id.commecial_partner_id.vat
                SubElement(reembolsos,
                           "codPaisPagoProveedorReembolso").text = reembolso.partner_id.commecial_partner_id.country_id and reembolso.partner_id.commecial_partner_id.country_id.sri_code or '593'
                SubElement(reembolsos,
                           "tipoProveedorReembolso").text = tipoIdentificacionComprador == '05' and '01' or '02'
                SubElement(reembolsos, "codDocReembolso").text = '01'
                agency, printer, sequence = reembolso.number.splai('-')
                SubElement(reembolsos, "estabDocReembolso").text = SubElement
                SubElement(reembolsos, "ptoEmiDocReembolso").text = printer
                SubElement(reembolsos, "secuencialDocReembolso").text = sequence
                fecha_emision = reembolso.date_invoice.strftime(util_model.get_formato_date())
                SubElement(reembolsos, "fechaEmisionDocReembolso").text = fecha_emision
                SubElement(reembolsos,
                           "numeroautorizacionDocReemb").text = reembolso.authorization_id and reembolso.authorization_id.number or reembolso.electronic_authorization
                detalleImpuestos = SubElement(reembolsos, "detalleImpuestos")
                tarifa_iva = reembolso['total_base_iva'] and round(
                    (reembolso['total_iva'] / reembolso['total_base_iva']),
                    2) or 0.0
                tipo_iva = '2'
                if tarifa_iva == 0.14:
                    tipo_iva = '3'
                if reembolso.total_base_iva_0 != 0:
                    self.get_total_impuestos(detalleImpuestos, '2', '0', reembolso.total_base_iva_0, 0.0,
                                             'detalleImpuesto', 0, True)
                if reembolso.total_base_iva != 0:
                    self.get_total_impuestos(detalleImpuestos, '2', tipo_iva, reembolso.total_base_iva,
                                             reembolso.total_iva, 'detalleImpuesto',
                                             int(tarifa_iva * 100), True, True)
                # if reembolso.total_base_no_iva != 0:
                #     self.get_total_impuestos(detalleImpuestos, '2', '6', reembolso.total_base_no_iva, 0.0,
                #                              'detalleImpuesto', 0, True)
        infoAdicional = SubElement(node, "infoAdicional")
        # TODO: agregar infoAdicional
        campoAdicional = SubElement(infoAdicional, "campoAdicional")
        campoAdicional.set("nombre", "OtroCampo")
        campoAdicional.text = "Otra Informacion"
        return node

AccountMove()


class AccountMoveLine(models.Model):
    _inherit = ["account.move.line", "ln10_ec.common.document.line"]
    _name = "account.move.line"

    l10n_ec_withhold_line_id = fields.Many2one(
        comodel_name='l10n_ec.withhold.line',
        string='Withhold Line',
        readonly=True)

    def _l10n_ec_get_discount_total(self):
        discount_total = self.price_unit * self.quantity * self.discount * 0.01
        return discount_total

    @api.depends(
        'price_unit', 'product_id', 'quantity', 'discount', 'tax_ids',
        'move_id.partner_id', 'move_id.currency_id',
        'move_id.company_id', 'move_id.invoice_date'
    )
    def _compute_l10n_ec_amounts(self):
        for move_line in self:
            move = move_line.move_id
            move_date = move.date or fields.Date.context_today(move)
            l10n_ec_base_iva_0 = 0.0
            l10n_ec_base_iva = 0.0
            l10n_ec_iva = 0.0
            price_unit_wo_discount = move_line.price_unit * (1 - (move_line.discount / 100.0))
            l10n_ec_discount_total = move_line._l10n_ec_get_discount_total()
            taxes_res = move_line.tax_ids._origin.compute_all(price_unit_wo_discount,
                quantity=move_line.quantity, currency=move.currency_id, product=move_line.product_id,
                partner=move.partner_id, is_refund=move.type in ('out_refund', 'in_refund'))
            # impuestos de iva 0 no agregan reparticion de impuestos,
            # por ahora se consideran base_iva_0, verificar esto
            if taxes_res['taxes']:
                for tax_data in taxes_res['taxes']:
                    tax = self.env['account.tax'].browse(tax_data['id'])
                    iva_group = self.env.ref('l10n_ec_niif.tax_group_iva')
                    if tax.tax_group_id.id == iva_group.id:
                        if tax_data['base'] != 0 and tax_data['amount'] == 0:
                            l10n_ec_base_iva_0 = tax_data['base']
                        else:
                            l10n_ec_base_iva = tax_data['base']
                            l10n_ec_iva = tax_data['amount']
            else:
                l10n_ec_base_iva_0 = taxes_res['total_excluded']
            move_line.l10n_ec_base_iva_0 = l10n_ec_base_iva_0
            move_line.l10n_ec_base_iva = l10n_ec_base_iva
            move_line.l10n_ec_iva = l10n_ec_iva
            move_line.l10n_ec_discount_total = l10n_ec_discount_total
            move_line.l10n_ec_base_iva_0_currency = move.currency_id._convert(
                l10n_ec_base_iva_0, move.company_currency_id, move.company_id, move_date)
            move_line.l10n_ec_base_iva_currency = move.currency_id._convert(
                l10n_ec_base_iva, move.company_currency_id, move.company_id, move_date)
            move_line.l10n_ec_iva_currency = move.currency_id._convert(
                l10n_ec_iva, move.company_currency_id, move.company_id, move_date)
            move_line.l10n_ec_discount_total_currency = move.currency_id._convert(
                l10n_ec_discount_total, move.company_currency_id, move.company_id, move_date)
