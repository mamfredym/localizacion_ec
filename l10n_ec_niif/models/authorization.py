# -*- coding: UTF-8 -*- #

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import Warning, RedirectWarning, ValidationError
from ..models import modules_mapping


class L10nECSriAuthorization(models.Model):

    _name = 'l10n_ec.sri.authorization'
    _description = 'S.R.I. Authorization'
    _rec_name = 'number'

    company_id = fields.Many2one('res.company', 'Company', required=True, help="",
                                 default=lambda self: self.env.user.company_id.id)
    active = fields.Boolean(string="Active?", default=True)
    number = fields.Char('Authorization Number',
                         size=10, required=True, index=True)
    start_date = fields.Date('Start Date', required=True)
    expiration_date = fields.Date('Expiration Date', required=True)
    line_ids = fields.One2many(comodel_name="l10n_ec.sri.authorization.line",
                               inverse_name="authorization_id", string="Document Types", required=False, )

    _sql_constraints = [('number_uniq', 'unique(company_id, number)', _('SRI Authorization must be unique by company'))]


L10nECSriAuthorization()

_DOCUMENT_NAMES = {
    'invoice': _('Invoice'),
    'withholding': _('Withhold'),
    'liquidation': _('Liquidation of Purchases'),
    'credit_note': _('Credit Note'),
    'debit_note': _('Debit Note'),
    'delivery_note': _('Delivery Note'),
}

class L10nECSriAuthorizationLine(models.Model):

    _name = 'l10n_ec.sri.authorization.line'
    _description = 'S.R.I. Authorization Document Type'

    _rec_name = 'document_type'

    def _get_available_type(self):
        types = [
            ('invoice', _('Invoice')),
            ('withholding', _('Withhold')),
            ('liquidation', _('Liquidation of Purchases')),
            ('credit_note', _('Credit Note')),
            ('debit_note', _('Debit Note')),
        ]
        if self.env['ir.module.module'].search([
            ('name', '=', 'l10n_ec_delivery_note'),
            ('state', '=', 'installed')
        ]):
            types.append(('delivery_note', 'Delivery Note'))
        return types

    document_type = fields.Selection(string="Document Type",
                                     selection='_get_available_type',
                                     required=True)
    first_sequence = fields.Integer('First Sequence')
    last_sequence = fields.Integer('Last Sequence')
    authorization_id = fields.Many2one(comodel_name="l10n_ec.sri.authorization",
                                       string="Authorization", required=True, ondelete='cascade')
    point_of_emission_id = fields.Many2one(comodel_name="l10n_ec.point.of.emission",
                                           string="Point of Emission", required=False, )
    agency_id = fields.Many2one(comodel_name="l10n_ec.agency",
                                string="Agency", related='point_of_emission_id.agency_id', store=True)
    padding = fields.Integer('Padding', default=9)

    @api.constrains(
        'first_sequence',
        'last_sequence',
    )
    def _check_sequence(self):
        for line in self:
            if line.last_sequence < 0 or line.first_sequence < 0:
                raise ValidationError(_("Number of sequence must be bigger than zero"))
            if line.last_sequence <= line.first_sequence:
                raise ValidationError(_("The first sequence %s must be lower than last sequence %s") % (line.first_sequence, line.last_sequence))

    @api.constrains(
        'padding',
                    )
    def _check_padding(self):
        for line in self:
            if line.padding < 0 or line.padding > 9:
                raise ValidationError(_("Padding must be between 0 or 9"))

    @api.constrains(
        'authorization_id',
        'printer_id',
        'name',
        'first_sequence',
        'last_sequence',
    )
    def _check_document_type(self):
        for line in self:
            domain = [
                ('document_type', '=', line.document_type),
                ('printer_id', '=', line.point_of_emission_id.id),
                ('id', '!=', line.id),
            ]
            other_recs = self.search(domain + [('authorization_id', '=', self.authorization_id.id)])
            if other_recs:
                raise ValidationError(_(
                    "There's another line with document type %s "
                    "for point of emission %s on agency %s to authorization %s") %
                                      (_DOCUMENT_NAMES.get(line.document_type), self.printer_id.display_name, self.agency_id.display_name,
                                       self.authorization_id.display_name))
            other_recs = self.search(domain)
            if other_recs:
                valid = True
                for other_auth in other_recs:
                    if line.first_sequence <= other_auth.first_sequence and line.last_sequence >= other_auth.last_sequence:
                        valid = False
                    if line.first_sequence >= other_auth.first_sequence and line.last_sequence <= other_auth.last_sequence:
                        valid = False
                    if other_auth.first_sequence <= line.last_sequence <= other_auth.last_sequence:
                        valid = False
                    if other_auth.last_sequence >= line.first_sequence >= other_auth.first_sequence:
                        valid = False
                if not valid:
                    raise ValidationError(_("There's another line with document type %s for "
                                            "point of emission %s in the agency %s, please check sequences") %
                                          (_DOCUMENT_NAMES.get(line.document_type),
                                           self.printer_id.display_name, self.agency_id.display_name))

    @api.model
    def validate_unique_value_document(self, invoice_type, document_number, company_id, res_id=False):
        company_model = self.env['res.company']
        if not document_number or not company_id:
            raise Warning(_("Verify the arguments to use the validate_unique_value_document function"))
        if not invoice_type:
            raise Warning(_("You must indicate what type of document it is, Invoice, Credit Note, Debit Note, etc."))
        document_type = modules_mapping.get_document_type(invoice_type)
        model_description = modules_mapping.get_document_name(document_type)
        model_name = modules_mapping.get_model_name(document_type)
        field_name = modules_mapping.get_field_name(document_type)
        domain = modules_mapping.get_domain(invoice_type, include_state=False)
        res_model = self.env[model_name]
        company = company_model.browse(company_id)
        domain.append((field_name, '=', document_number))
        domain.append(('company_id', '=', company_id))
        if res_id:
            domain.append(('id', '!=', res_id))
        model_recs = res_model.search(domain)
        if model_recs:
            if isinstance(res_id, models.NewId):
                if model_recs and len(model_recs) <= 1:
                    return True
            raise Warning(_("There is another document type %s with number '%s' for the company %s") % (
                model_description, document_number, company.name))
        return True

    @api.model
    def fill_padding(self, number, padding):
        return str(number).rjust(padding, '0')

    @api.model
    def create_number(self, printer_id, number):
        result = ''
        if printer_id:
            printer = self.env['l10n_ec.point.of.emission'].browse(printer_id)
            result = printer.agency_id.number + '-' + printer.number + '-' + self.fill_padding(number, 9)
        return result

    @api.model
    def complete_number(self, printer_id, number):
        printer = self.env['l10n_ec.point.of.emission'].browse(printer_id)
        aux = number.split('-')
        res = number
        if number:
            if len(aux) == 3:
                try:
                    seq = self.fill_padding(int(aux[2]), 9)
                    res = "%s-%s-%s" % (printer.agency_id.number, printer.number, seq)
                except Exception as e:
                    res = number
            elif len(aux) == 1:
                try:
                    seq = self.fill_padding(int(number), 9)
                    res = "%s-%s-%s" % (printer.agency_id.number, printer.number, seq)
                except Exception as e:
                    res = number
        return res

    @api.model
    def get_next_value_sequence(self, invoice_type, date, company_id, printer_id, raise_exception=False):
        if not invoice_type or not company_id or not printer_id:
            return False, False
        if not date:
            date = fields.Date.context_today(self)
        printer_model = self.env['l10n_ec.point.of.emission']
        document_type = modules_mapping.get_document_type(invoice_type)
        model_name = modules_mapping.get_model_name(document_type)
        field_name = modules_mapping.get_field_name(document_type)
        model_description = modules_mapping.get_document_name(document_type)
        res_model = self.env[model_name]
        printer = printer_model.browse(printer_id)
        doc_recs = self.search([
            ('document_type', '=', document_type),
            ('printer_id', '=', printer_id),
            ('authorization_id.start_date', '<=', date),
            ('authorization_id.expiration_date', '>=', date),
        ], order="first_sequence")
        start_doc_number = "%s-%s-%s" % (printer.agency_id.number, printer.number, '%')
        domain = modules_mapping.get_domain(invoice_type, include_state=False) + [
            (field_name, 'like', start_doc_number)]
        recs_finded = res_model.search(domain, order=field_name + ' DESC', limit=1)
        doc_finded = None
        last_number = False
        seq = False
        if recs_finded:
            last_number = recs_finded[0][field_name]
        try:
            if last_number:
                seq = int(last_number.split('-')[2])
            if self.env.context.get('numbers_skip', []):
                seq = int(sorted(self.env.context.get('numbers_skip', []))[-1].split('-')[2])
        except Exception as e:
            seq = False
        if doc_recs:
            for doc in doc_recs:
                if date >= doc.authorization_id.start_date:
                    if seq and doc.first_sequence <= seq < doc.last_sequence:
                        last_number = self.create_number(doc.printer_id.id, seq + 1)
                        doc_finded = doc.id
                        break
                    elif seq and seq == doc.last_sequence:
                        last_number = "%s-%s-" % (printer.agency_id.number, printer.number)
                        doc_finded = doc.id
                        break
                    elif not seq:
                        last_number = self.create_number(doc.printer_id.id, doc.first_sequence)
                        doc_finded = doc.id
                        break
            if not doc_finded and recs_finded:
                try:
                    seq = int(last_number.split('-')[2])
                except Exception as e:
                    seq = False
                if seq:
                    for doc in doc_recs:
                        if doc.first_sequence > seq and date >= doc.authorization_id.start_date:
                            last_number = self.create_number(doc.printer_id.id, doc.first_sequence)
                            doc_finded = doc.id
                            break
                    if not doc_finded:
                        last_number = ""
                else:
                    last_number = ""
        else:
            last_number = ""
        if not doc_finded and raise_exception:
            raise Warning(_(
                "It is not possible to find authorization for the document type %s "
                "at the point of issue %s for the agency %s with date %s") %
                          (model_description, printer.number, printer.agency_id.number, date))
        return last_number, doc_finded and doc_finded or False


L10nECSriAuthorizationLine()
