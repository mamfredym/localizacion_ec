# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare, float_round
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
                                                     store=True, compute='_get_l10n_ec_identification_type',
                                                     compute_sudo=True)
    l10n_ec_tax_support_domain_ids = fields.Many2many(comodel_name="l10n_ec.tax.support",
                                                      string="Tax Support Domain",
                                                      compute='_get_l10n_ec_identification_type',
                                                      compute_sudo=True)

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
                                             required=False, default=False)
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
        type = values.get('type', self.type)
        if type in ('out_invoice', 'out_refund', 'in_invoice'):
            invoice_type = modules_mapping.get_invoice_type(type,
                                                            values.get('l10n_ec_debit_note', self.l10n_ec_debit_note),
                                                            values.get('l10n_ec_liquidation', self.l10n_ec_liquidation))
            if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out', 'liquidation'):
                default_printer = self.env['res.users']. \
                    get_default_point_of_emission(self.env.user.id, raise_exception=True).get('default_printer_default_id')
                values['l10n_ec_point_of_emission_id'] = default_printer.id
                if default_printer:
                    values['l10n_ec_type_emission'] = default_printer.type_emission
                    next_number, auth_line = default_printer.get_next_value_sequence(invoice_type, False, False)
                    if next_number:
                        values['l10n_latam_document_number'] = next_number
                    if auth_line:
                        values['l10n_ec_authorization_line_id'] = auth_line.id
        return values

    def copy(self, default=None):
        if not default:
            default = {}
        if self.filtered(lambda x: x.company_id.country_id.code == 'EC'):
            invoice_type = modules_mapping.get_invoice_type(self.type, self.l10n_ec_debit_note, self.l10n_ec_liquidation)
            next_number, auth_line = self.l10n_ec_point_of_emission_id.get_next_value_sequence(invoice_type, False, False)
            default['l10n_latam_document_number'] = next_number
            default['l10n_ec_authorization_line_id'] = auth_line.id
        return super(AccountMove, self).copy(default)

    @api.onchange(
        'type',
        'l10n_ec_debit_note',
        'l10n_ec_liquidation',
        'l10n_ec_point_of_emission_id',
    )
    def _onchange_point_of_emission(self):
        for move in self.filtered(lambda x: x.company_id.country_id.code == 'EC' and x.type
                                            in ('out_invoice', 'out_refund', 'in_invoice')):
            if move.l10n_ec_point_of_emission_id:
                invoice_type = modules_mapping.get_invoice_type(move.type, move.l10n_ec_debit_note,
                                                                move.l10n_ec_liquidation)
                if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out', 'liquidation'):
                    next_number, auth_line = move.l10n_ec_point_of_emission_id.get_next_value_sequence(invoice_type, False, False)
                    if next_number:
                        move.l10n_latam_document_number = next_number
                    if auth_line:
                        move.l10n_ec_authorization_line_id = auth_line.id

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
                modules_mapping.get_invoice_type(move.type, move.l10n_ec_debit_note, move.l10n_ec_liquidation),
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
                                                            self.env.context.get('default_l10n_ec_debit_note', False),
                                                            self.env.context.get('default_l10n_ec_liquidation', False))
            if invoice_type in ('debit_note_in', 'debit_note_out', 'liquidation'):
                journal = journal_model.search([
                    ('company_id', '=', self._context.get('default_company_id', self.env.company.id)),
                    ('l10n_ec_extended_type', '=', invoice_type),
                ])
                if journal:
                    return super(AccountMove, self.with_context(default_journal_id=journal.id))._get_default_journal()
        return super(AccountMove, self)._get_default_journal()

    #FIXME: When function is called by default, only call first function, not hierachy
    journal_id = fields.Many2one(default=_get_default_journal)

    @api.onchange(
        'l10n_ec_original_invoice_id',
        'invoice_date',
                  )
    def onchange_l10n_ec_original_invoice(self):
        line_model = self.env['account.move.line'].with_context(check_move_validity=False)
        if self.l10n_ec_original_invoice_id:
            lines = line_model.browse()
            default_move = {
                'ref': _('Reversal'),
                'date': self.invoice_date or fields.Date.context_today(self),
                'invoice_date': self.invoice_date or fields.Date.context_today(self),
                'journal_id': self.journal_id and self.journal_id.id,
                'invoice_payment_term_id': None,
            }
            move_vals = self.l10n_ec_original_invoice_id._reverse_move_vals(default_move)
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

    l10n_ec_consumidor_final = fields.Boolean(string="Consumidor Final", compute="_get_l10n_ec_consumidor_final")

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
                    raise UserError(_("You can't make refund to final customer on ecuadorian company"))
                if move.l10n_ec_consumidor_final and move.type in ('in_refund', 'in_invoice'):
                    raise UserError(_("You can't make bill or refund to final customer on ecuadorian company"))

        return super(AccountMove, self).action_post()

    def unlink(self):
        if self.env.context.get('skip_recurtion', False):
            return super(AccountMove, self).unlink()
        for move in self:
            if move.company_id.country_id.code == 'EC':
                if move.type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                    if move.state != 'draft':
                        raise UserError(_("You only delete invoices in draft state"))
                    else:
                        move.with_context(skip_recurtion=True, force_delete=True).unlink()

    @api.depends(
        'line_ids.price_subtotal',
        'line_ids.tax_base_amount',
        'line_ids.tax_line_id',
        'partner_id',
        'currency_id'
    )
    def _compute_l10n_ec_amounts(self):
        for rec in self:
            l10n_ec_base_iva_0 = 0
            l10n_ec_base_iva = 0
            l10n_ec_iva = 0
            for group in rec.amount_by_group:
                iva_group = self.env.ref('l10n_ec_niif.tax_group_iva')
                if group[6] == iva_group.id:
                    if group[2] != 0 and group[1] == 0:
                        l10n_ec_base_iva_0 = group[2]
                    else:
                        l10n_ec_base_iva = group[2]
                        l10n_ec_iva = group[1]
            rec.l10n_ec_base_iva_0 = l10n_ec_base_iva_0
            rec.l10n_ec_base_iva = l10n_ec_base_iva
            rec.l10n_ec_iva = l10n_ec_iva


    l10n_ec_base_iva = fields.Float(
        string='Base IVA',
        compute="_compute_l10n_ec_amounts",
        store=True)

    l10n_ec_base_iva_0 = fields.Float(
        string='Base IVA 0',
        compute="_compute_l10n_ec_amounts",
        store=True)

    l10n_ec_iva = fields.Float(
        string='IVA',
        compute="_compute_l10n_ec_amounts",
        store=True)


AccountMove()

