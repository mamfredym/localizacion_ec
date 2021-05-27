import logging
import re
from datetime import datetime, time

import requests

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from ..models import modules_mapping

_logger = logging.getLogger(__name__)


class L10nECSriAuthorizationSupplier(models.Model):

    _name = "l10n_ec.sri.authorization.supplier"
    _description = "S.R.I. Authorization Suppliers"

    def _get_document_type(self):
        output = []
        doc_names = {
            "in_invoice": _("Invoice"),
            "withholding": _("Withhold"),
            "liquidation": _("Liquidation of purchases"),
            "in_refund": _("Credit Note"),
            "debit_note_in": _("Debit Note"),
            "delivery_note": _("Delivery Note"),
        }
        if not self.env.context.get("document_type", False):
            for doc in doc_names.keys():
                output.append((doc, doc_names.get(doc)))
        else:
            doc_name = self.env.context.get("document_type", False)
            output.append((doc_name, doc_names.get(doc_name, "No Name")))
        return output

    @api.constrains("agency", "printer_point")
    def _check_agency_pp(self):
        cadena = r"(\d{3})"
        for auth in self:
            if auth.agency and not re.match(cadena, auth.agency):
                raise ValidationError(_("Invalid Number Format, this must be like 001"))
            if auth.printer_point and not re.match(cadena, auth.printer_point):
                raise ValidationError(_("Invalid Number Format, this must be like 001"))

    @api.constrains(
        "number",
    )
    def _check_number(self):
        cadena = r"(\d{10})"
        for auth in self:
            if auth.number and not re.match(cadena, auth.number):
                raise ValidationError(_("Invalid Format Number, this must be like 0123456789"))

    @api.constrains("start_date", "expiration_date")
    def _check_dates(self):
        for auth in self:
            if auth.start_date >= auth.expiration_date:
                raise ValidationError(
                    _("The dates of authorization of supplier %s " "must be valid start: %s end: %s")
                    % (auth.number, auth.start_date, auth.expiration_date)
                )

    @api.constrains(
        "number",
        "first_sequence",
        "last_sequence",
        "document_type",
        "agency",
        "printer_point",
        "start_date",
        "expiration_date",
    )
    def _check_sequence(self):
        for auth in self:
            if auth.first_sequence < 0 and not auth.autoprinter:
                raise ValidationError(
                    _("First sequence must be bigger than zero, please check authorization %s") % auth.display_name
                )
            if auth.last_sequence < 0 and not auth.autoprinter:
                raise ValidationError(
                    _("Last sequence must be bigger than zero, please check authorization %s") % auth.display_name
                )
            if auth.first_sequence >= auth.last_sequence and not auth.autoprinter:
                raise ValidationError(
                    _(
                        "First sequence must be bigger than last sequence, "
                        "please check the authorization %s start: % last:%s"
                    )
                    % (auth.display_name, auth.first_sequence, auth.last_sequence)
                )
            elif not auth.autoprinter:
                args = [
                    ("commercial_partner_id", "=", auth.commercial_partner_id.id),
                    ("number", "=", auth.number),
                    ("document_type", "=", auth.document_type),
                    ("agency", "=", auth.agency),
                    ("printer_point", "=", auth.printer_point),
                ]
                if not isinstance(auth.id, models.NewId):
                    args.append(("id", "!=", auth.id))
                other_auth_recs = auth.search(args)
                is_valid = True
                for other_auth in other_auth_recs:
                    if (
                        auth.first_sequence <= other_auth.first_sequence
                        and auth.last_sequence >= other_auth.last_sequence
                    ):
                        is_valid = False
                    if (
                        auth.first_sequence >= other_auth.first_sequence
                        and auth.last_sequence <= other_auth.last_sequence
                    ):
                        is_valid = False
                    if other_auth.first_sequence <= auth.last_sequence <= other_auth.last_sequence:
                        is_valid = False
                    if other_auth.last_sequence >= auth.first_sequence >= other_auth.first_sequence:
                        is_valid = False
                if not is_valid:
                    raise ValidationError(
                        _(
                            "There's another authorization in same periods, "
                            "please check the authorization on partner %s"
                        )
                        % auth.display_name
                    )

    @api.constrains("padding")
    def _check_padding(self):
        for auth in self:
            if auth.padding < 0 or auth.padding > 9:
                raise ValidationError(_("Padding number must be between 0 and 9"))

    def _check_document_in_use(self, vals):
        invoice_model = self.env["account.move"]
        retention_model = self.env["l10n_ec.withhold"]
        invoice_recs, retention_recs = [], []
        has_change = False
        fields_to_inspect = [
            "number",
            "agency",
            "printer_point",
            "start_date",
            "expiration_date",
            "first_sequence",
            "last_sequence",
        ]
        for auth in self:
            has_change = False
            # cuando se modifica los datos de un o2m, se pasan todos los datos, asi no haya modificaciones, consideraria que esto deberia solucionarse a nivel de ORM
            # mientras, hacer la validacion solo cuando se cambien datos realmente
            for f in fields_to_inspect:
                if f in vals and vals[f] != auth[f]:
                    has_change = True
                    break
            if has_change:
                # buscar si hay algun documento activo que utilice esta autorizacion, para no permitir su modificacion
                # no hay dependencia a retenciones, asi que no simpre va a estar instalado este modulo
                if retention_model:
                    retention_recs = retention_model.search(
                        [  # TODO: filtrar estado???
                            ("state", "not in", ("draft", "canceled")),
                            ("authorization_sale_id", "in", self.ids),
                        ]
                    )
                invoice_recs = invoice_model.search(
                    [  # TODO: filtrar estado???
                        ("state", "not in", ("draft", "cancel")),
                        ("l10n_ec_supplier_authorization_id", "in", self.ids),
                    ]
                )
                if invoice_recs or retention_recs:
                    raise UserError(
                        _(
                            "You cannot modify authorization %s of partner %s, "
                            "this is already used in active documents, contact de system administrator"
                        )
                        % (auth.display_name, auth.partner_id.display_name)
                    )
        return True

    _rec_name = "number"

    partner_id = fields.Many2one(
        "res.partner",
        "Partner",
        required=False,
        index=True,
        auto_join=True,
        help="",
    )
    commercial_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Commercial partner",
        related="partner_id.commercial_partner_id",
        store=True,
    )
    number = fields.Char(
        "Number",
        size=10,
        required=True,
        readonly=False,
        index=True,
        help="",
    )
    document_type = fields.Selection(
        "_get_document_type",
        string="Document Type",
        required=True,
        default=lambda self: self.env.context.get("document_type", False),
    )
    agency = fields.Char(
        "Agency",
        size=3,
        required=True,
        readonly=False,
        help="",
    )
    printer_point = fields.Char(
        "Point of Emission",
        size=3,
        required=True,
        readonly=False,
        help="",
    )
    start_date = fields.Date(
        "Start Date",
        required=True,
        help="",
    )
    expiration_date = fields.Date(
        "Expiration Date",
        required=True,
        help="",
    )
    first_sequence = fields.Integer(
        "First Sequence",
        help="",
    )
    last_sequence = fields.Integer(
        "Last Sequence",
        help="",
    )
    padding = fields.Integer(
        "Padding",
        default=lambda *a: 9,
        help="",
    )
    autoprinter = fields.Boolean(
        "Autoprinter?",
        readonly=False,
        help="",
        default=lambda self: self.env.context.get("type_emission", False) == "auto_printer",
    )

    @api.model
    def check_number_document(self, invoice_type, number, authorization, date=None, res_id=None, foreign=False):
        if not invoice_type:
            raise UserError(_("You must declare document type to check authorization"))
        if not number:
            raise UserError(_("You must declare document number to check authorization"))
        if not authorization and not foreign and not self.env.context.get("from_refund"):
            raise UserError(_("You must declare authorization to check"))
        if foreign:
            return True
        number_split = number.split("-")
        if len(number_split) != 3:
            raise UserError(_("Invalid Number, that must be like 001-001-0123456789"))
        num_shop, num_printer, num_doc = number_split
        try:
            num_doc = int(num_doc)
        except ValueError:
            if not foreign:
                raise UserError(
                    _(
                        "The number of document must be numeric, "
                        "please don't input letters, or check if partner is not ecuadorian"
                    )
                )
        document_type = modules_mapping.get_document_type(invoice_type)
        model_name = modules_mapping.get_model_name(document_type)
        description_name = modules_mapping.get_document_name(document_type)
        field_name = modules_mapping.get_field_name(document_type)
        res_model = self.env[model_name]
        partner = authorization and authorization.partner_id or None
        partner_id = partner and partner.id or False
        other_recs = []
        if not foreign:
            if not date:
                date = fields.Date.context_today(self)
            if date > authorization.expiration_date or date < authorization.start_date:
                raise UserError(
                    _("%s is not within the authorization dates %s y %s")
                    % (date, authorization.start_date, authorization.expiration_date)
                )
            if num_shop != authorization.agency:
                raise UserError(
                    _("The agency number %s does not correspond to the authorization, that should be %s")
                    % (num_shop, authorization.agency)
                )
            if num_printer != authorization.printer_point:
                raise UserError(
                    _("The emission point number %s does not correspond to the authorization, that should be %s")
                    % (num_printer, authorization.printer_point)
                )
            if (
                num_doc < authorization.first_sequence
                or num_doc > authorization.last_sequence
                and not authorization.autoprinter
            ):
                raise UserError(
                    _("The sequence number %s is not within the range %s and %s")
                    % (
                        num_doc,
                        authorization.first_sequence,
                        authorization.last_sequence,
                    )
                )
        if number:
            if partner_id:
                # FIX: no usar like ya que si tengo un documento 001-001-00000004
                # y el numero a validar es 001-001-000000044
                # va a considerar como que coinciden
                # no usar states en la validacion de que los documentos no se dupliquen por numero o si??
                domain = modules_mapping.get_domain(invoice_type, include_state=False)
                other_recs = res_model.search(domain + [(field_name, "=", number), ("partner_id", "=", partner_id)])
        if not foreign:
            if isinstance(res_id, models.NewId):
                # FIXME: en caso de venir de un onchange, no debe validar duplicidad?
                return True
            list_ids_exist = []
            if other_recs:
                for other_rec in other_recs:
                    if other_rec.id != res_id:
                        list_ids_exist.append(other_rec)
            if list_ids_exist and partner:
                raise UserError(
                    _("There is another document of type %s with number '%s' for partner %s")
                    % (description_name, number, partner.name)
                )
        return True

    def write(self, values):
        if self._uid != SUPERUSER_ID and not self.env.user.has_group("base.group_system"):
            self._check_document_in_use(values)
        return super(L10nECSriAuthorizationSupplier, self).write(values)

    @api.model
    def validate_unique_document_partner(self, invoice_type, number, partner_id, res_id=None):
        if not number or not partner_id:
            raise UserError(_("Check parameters of partner and number to continue"))
        if not invoice_type:
            raise UserError(_("You must specify type of document to continue."))
        partner_model = self.env["res.partner"]
        document_type = modules_mapping.get_document_type(invoice_type)
        model_name = modules_mapping.get_model_name(document_type)
        field_name = modules_mapping.get_field_name(document_type)
        model_description = modules_mapping.get_document_name(document_type)
        res_model = self.env[model_name]
        partner = partner_model.browse(partner_id)
        # FIX: no usar like ya que si tengo un documento 001-001-00000004
        # y el numero a validar es 001-001-000000044
        # va a considerar como que coinciden
        # debe ser el numero completo incluyendo agencia y punto de emision 001-001-0000001
        number_criteria = [(field_name, "=", str(number))]
        args = (
            modules_mapping.get_domain(invoice_type, include_state=False)
            + [("partner_id", "=", partner_id)]
            + number_criteria
        )
        if res_id:
            args.append(("id", "!=", res_id))
        model_recs = number and res_model.search(args) or False
        if model_recs:
            raise UserError(
                _("There's another document type %s with number '%s' for partner %s")
                % (model_description, number, partner.name)
            )
        return True

    @api.model
    def fill_padding(self, number, padding):
        return str(number).rjust(padding, "0")

    @api.model
    def get_supplier_authorizations(self, invoice_type, partner_id, number=None, date=None):
        partner_model = self.env["res.partner"]
        res = {
            "message": "",
            "multi_auth": False,
            "res_number": "",
        }
        if not invoice_type or not partner_id:
            return res
        if not date:
            date = fields.Date.context_today(self)
        document_type = modules_mapping.get_document_type(invoice_type)
        model_description = modules_mapping.get_document_name(document_type)
        partner = partner_model.browse(partner_id)
        message = ""
        criteria = [
            ("start_date", "<=", date),
            ("expiration_date", ">=", date),
            ("document_type", "=", invoice_type),
            ("partner_id", "=", partner_id),
        ]
        agency, printer_point, seq_number = "", "", ""
        if number:
            try:
                agency, printer_point, seq_number = number.split("-")
                agency = agency.rjust(3, "0")
                printer_point = printer_point.rjust(3, "0")
                seq_number = int(seq_number)
            except Exception:
                try:
                    seq_number = int(number)
                except Exception:
                    return res
        if agency and printer_point:
            criteria.append(("agency", "=", agency))
            criteria.append(("printer_point", "=", printer_point))
        if seq_number:
            criteria.append(("first_sequence", "<=", seq_number))
            criteria.append(("last_sequence", ">=", seq_number))
        auth_recs = self.search(criteria, order="expiration_date ASC")
        if not auth_recs:
            if seq_number:
                criteria.append(("first_sequence", "<=", seq_number))
                criteria.append(("last_sequence", ">=", seq_number))
            auth_recs = self.search(criteria, order="expiration_date ASC")
            if not auth_recs:
                if not seq_number:
                    message += _(
                        "There's no exist authorization for document type %s for partner %s with date %s, "
                        "check if you should create authorization"
                    ) % (model_description, partner.name, date)
                else:
                    message += _(
                        "There's no exist authorization for document type %s "
                        "for partner %s with date %s for sequence %s, "
                        "check if you should create authorization"
                    ) % (model_description, partner.name, date, seq_number)
                res.update({"message": message})
        res.update(
            {
                "auth_ids": auth_recs.ids,
            }
        )
        if len(auth_recs) > 1:
            message += _(
                "There is more than one match of active authorizations for the partner %s of type %s "
                "for the number %s with date %s, please select the correct "
                "authorization and then enter the number"
            ) % (partner.display_name, model_description, number, date)
            res.update(
                {
                    "multi_auth": True,
                    "message": message,
                }
            )
        if len(auth_recs) == 1 and seq_number:
            res_number = (
                auth_recs.agency
                + "-"
                + auth_recs.printer_point
                + "-"
                + self.fill_padding(seq_number, auth_recs.padding)
            )
            res.update({"res_number": res_number})
        return res

    def name_get(self):
        res = []
        for rec in self:
            name = "{} ({} - {})".format(rec.number, rec.agency, rec.printer_point)
            res.append((rec.id, name))
        return res

    @api.model
    def validate_authorization_into_sri(
        self,
        authorization_number,
        partner_vat,
        document_type,
        document_number,
        document_date,
    ):
        response_json = {}
        document_types_sri = {
            "in_invoice": "FAC",
            "withholding": "CDR",
            "liquidation": "LCB",
            "in_refund": "NDC",
            "debit_note_in": "NDD",
            "delivery_note": "GRD",
        }
        try:
            if not isinstance(document_date, datetime):
                document_date = datetime.combine(document_date, time.max)
            tipoDocumento = document_types_sri.get(document_type)
            params = {
                "tipoDocumento": tipoDocumento,
                "autorizacion": authorization_number,
                "emision": int(document_date.timestamp() * 1000),
                "ruc": partner_vat,
            }
            response = requests.get(
                f"https://srienlinea.sri.gob.ec/movil-servicios/api/v1.0/documentoValido/{document_number}",
                params=params,
            )
            response_json = response.json()
        except Exception as e:
            _logger.info("Error Validating authorization into sri: %s" % str(e))
        return response_json


L10nECSriAuthorizationSupplier()
