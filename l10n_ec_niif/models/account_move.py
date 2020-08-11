from xml.etree.ElementTree import SubElement

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare, float_is_zero, float_round
from odoo.tools.safe_eval import safe_eval

from ..models import modules_mapping


class L10nECIdentificationType(models.Model):

    _name = "l10n_ec.identification.type"

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True)
    document_type_ids = fields.Many2many(
        "l10n_latam.document.type", string="Tipos de Transacciones Asociadas"
    )
    sale_invoice_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Sales Document Type for Invoices",
        required=False,
    )
    sale_credit_note_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Sales Document Type for Credit Notes",
        required=False,
    )
    sale_debit_note_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Sales Document Type for Debit Notes",
        required=False,
    )
    purchase_invoice_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Purchases Document Type for Invoices",
        required=False,
    )
    purchase_credit_note_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Purchases Document Type for Credit Notes",
        required=False,
    )
    purchase_debit_note_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Purchases Document Type for Debit Notes",
        required=False,
    )
    purchase_liquidation_document_type_id = fields.Many2one(
        comodel_name="l10n_latam.document.type",
        string="Default Document Type for Purchase's Liquidation",
        required=False,
    )

    def _name_search(
        self, name, args=None, operator="ilike", limit=100, name_get_uid=None
    ):
        args = args or []
        recs = self.browse()
        res = super(L10nECIdentificationType, self)._name_search(
            name, args, operator, limit, name_get_uid
        )
        if not res and name:
            recs = self.search([("name", operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search([("code", operator, name)] + args, limit=limit)
            if recs:
                res = (
                    models.lazy_name_get(self.browse(recs.ids).with_user(name_get_uid))
                    or []
                )
        return res

    def name_get(self):
        res = []
        for r in self:
            name = "{} - {}".format(r.code, r.name)
            res.append((r.id, name))
        return res


class AccountMove(models.Model):
    _inherit = [
        "account.move",
        "l10n_ec.common.document",
        "l10n_ec.common.document.electronic",
    ]
    _name = "account.move"

    @api.depends(
        "type",
        "l10n_ec_point_of_emission_id",
        "l10n_ec_debit_note",
        "l10n_ec_liquidation",
    )
    def _compute_l10n_ec_is_environment_production(self):
        xml_model = self.env["sri.xml.data"]
        for invoice in self:
            if invoice.is_invoice():
                invoice_type = invoice.l10n_ec_get_invoice_type()
                invoice.l10n_ec_is_environment_production = xml_model.l10n_ec_is_environment_production(
                    invoice_type, invoice.l10n_ec_point_of_emission_id
                )
            else:
                invoice.l10n_ec_is_environment_production = False

    l10n_ec_is_environment_production = fields.Boolean(
        "Es Ambiente de Produccion?",
        compute="_compute_l10n_ec_is_environment_production",
        store=True,
        index=True,
    )
    l10n_ec_original_invoice_id = fields.Many2one(
        comodel_name="account.move", string="Original Invoice"
    )
    l10n_ec_credit_note_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="l10n_ec_original_invoice_id",
        string="Credit Notes",
        required=False,
    )
    l10n_ec_refund_ids = fields.One2many(
        comodel_name="l10n_ec.account.invoice.refund",
        inverse_name="invoice_id",
        string="Refunds",
        required=False,
    )
    l10n_ec_tax_support_id = fields.Many2one(
        comodel_name="l10n_ec.tax.support", string="Tax Support", required=False,
    )
    l10n_ec_is_exportation = fields.Boolean(string="Is Exportation?")
    l10n_ec_tipo_regimen_pago_exterior = fields.Selection(
        [
            ("01", "Régimen general"),
            ("02", "Paraíso fiscal"),
            ("03", "Régimen fiscal preferente o jurisdicción de menor imposición"),
        ],
        string="Tipo de regimen fiscal del exterior",
        states={},
        help="",
    )
    l10n_ec_aplica_convenio_doble_tributacion = fields.Selection(
        [("si", "SI"), ("no", "NO"),],
        string="Aplica convenio doble tributación",
        states={},
        help="",
    )
    l10n_ec_pago_exterior_sujeto_retencion = fields.Selection(
        [("si", "SI"), ("no", "NO"),],
        string="Pago sujeto a retención",
        states={},
        help="",
    )
    l10n_ec_sri_payment_id = fields.Many2one(
        "l10n_ec.sri.payment.method",
        "SRI Payment Method",
        default=lambda self: self.env.company.l10n_ec_sri_payment_id,
    )
    l10n_ec_foreign = fields.Boolean(
        "Foreign?", related="partner_id.l10n_ec_foreign", store=True
    )
    l10n_ec_debit_note = fields.Boolean(
        string="Debit Note?",
        default=lambda self: self.env.context.get("default_l10n_ec_debit_note", False),
    )
    l10n_ec_liquidation = fields.Boolean(
        string="Liquidation of Purchases?",
        default=lambda self: self.env.context.get("default_l10n_ec_liquidation", False),
    )
    l10n_ec_rise = fields.Char("R.I.S.E", copy=False)
    l10n_ec_legacy_document = fields.Boolean(
        string="Is External Doc. Modified?",
        help="With this option activated, the system will not require an invoice to issue the Debut or Credit Note",
    )
    l10n_ec_legacy_document_date = fields.Date(string="External Document Date")
    l10n_ec_legacy_document_number = fields.Char(string="External Document Number")
    l10n_ec_legacy_document_authorization = fields.Char(
        string="External Authorization Number", size=49
    )
    l10n_ec_credit_days = fields.Integer(
        string="Días Crédito", compute="_compute_l10n_ec_credit_days", store=True
    )

    @api.constrains("l10n_ec_legacy_document_number", "l10n_latam_document_type_id")
    @api.onchange("l10n_ec_legacy_document_number", "l10n_latam_document_type_id")
    def _check_l10n_ec_legacy_document_number(self):
        for invoice in self:
            if (
                invoice.l10n_ec_legacy_document_number
                and invoice.l10n_latam_document_type_id
            ):
                invoice.l10n_latam_document_type_id._format_document_number(
                    invoice.l10n_ec_legacy_document_number
                )

    @api.depends("invoice_date", "invoice_date_due")
    def _compute_l10n_ec_credit_days(self):
        now = fields.Date.context_today(self)
        for invoice in self:
            date_invoice = invoice.invoice_date or now
            date_due = invoice.invoice_date_due or date_invoice
            invoice.l10n_ec_credit_days = (date_due - date_invoice).days

    @api.depends(
        "partner_id.l10n_ec_type_sri",
        "l10n_ec_point_of_emission_id",
        "l10n_ec_is_exportation",
        "l10n_ec_debit_note",
        "l10n_ec_liquidation",
        "type",
        "company_id",
    )
    def _compute_l10n_ec_identification_type(self):
        def get_identification(code):
            identification_model = self.env["l10n_ec.identification.type"]
            identification = identification_model.search([("code", "=", code)])
            return identification and identification.id or False

        tax_support_model = self.env["l10n_ec.tax.support"]
        for move in self:
            if move.company_id.country_id.code == "EC":
                supports = tax_support_model.sudo()
                if move.partner_id.l10n_ec_type_sri:
                    if move.type in ("in_invoice", "in_refund"):
                        if move.partner_id.l10n_ec_type_sri == "Ruc":
                            move.l10n_ec_identification_type_id = get_identification(
                                "01"
                            )
                        elif move.partner_id.l10n_ec_type_sri == "Cedula":
                            move.l10n_ec_identification_type_id = get_identification(
                                "02"
                            )
                        elif move.partner_id.l10n_ec_type_sri == "Pasaporte":
                            move.l10n_ec_identification_type_id = get_identification(
                                "03"
                            )
                        else:
                            move.l10n_ec_identification_type_id = False
                    elif move.type in ("out_invoice", "out_refund"):
                        if not move.l10n_ec_is_exportation:
                            if move.partner_id.l10n_ec_type_sri == "Ruc":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "04"
                                )
                            elif move.partner_id.l10n_ec_type_sri == "Cedula":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "05"
                                )
                            elif move.partner_id.l10n_ec_type_sri == "Pasaporte":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "06"
                                )
                            elif move.partner_id.l10n_ec_type_sri == "Consumidor":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "07"
                                )
                            else:
                                move.l10n_ec_identification_type_id = False
                        else:
                            if move.partner_id.l10n_ec_type_sri == "Ruc":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "20"
                                )
                            elif move.partner_id.l10n_ec_type_sri == "Pasaporte":
                                move.l10n_ec_identification_type_id = get_identification(
                                    "21"
                                )
                            else:
                                move.l10n_ec_identification_type_id = False
                else:
                    move.l10n_ec_identification_type_id = False
                if move.l10n_ec_identification_type_id:
                    latam_type = "invoice"
                    if move.type in ("out_refund", "in_refund"):
                        latam_type = "credit_note"
                    if move.l10n_ec_debit_note:
                        latam_type = "debit_note"
                    move.l10n_latam_available_document_type_ids = [
                        (
                            6,
                            0,
                            move.l10n_ec_identification_type_id.document_type_ids.filtered(
                                lambda x: x.internal_type == latam_type
                            ).ids,
                        )
                    ]
                    if (
                        move.l10n_latam_available_document_type_ids
                        and move.l10n_latam_document_type_id.id
                        not in move.l10n_latam_available_document_type_ids.ids
                    ):
                        if move.type == "in_invoice":
                            move.l10n_latam_document_type_id = (
                                move.purchase_invoice_document_type_id.id
                            )
                        elif move.type == "in_refund":
                            move.l10n_latam_document_type_id = (
                                move.purchase_credit_note_document_type_id.id
                            )
                        elif move.type == "out_invoice":
                            move.l10n_latam_document_type_id = (
                                move.sale_invoice_document_type_id.id
                            )
                        elif move.type == "out_refund":
                            move.l10n_latam_document_type_id = (
                                move.sale_credit_note_document_type_id.id
                            )
                    if move.l10n_latam_document_type_id:
                        supports = tax_support_model.search(
                            [
                                (
                                    "document_type_ids",
                                    "in",
                                    move.l10n_latam_document_type_id.ids,
                                )
                            ]
                        )
                else:
                    move.l10n_latam_available_document_type_ids = []
                if supports:
                    move.l10n_ec_tax_support_domain_ids = supports.ids
                else:
                    move.l10n_ec_tax_support_domain_ids = []
            else:
                move.l10n_latam_available_document_type_ids = []
                move.l10n_ec_tax_support_domain_ids = []

    l10n_ec_identification_type_id = fields.Many2one(
        "l10n_ec.identification.type",
        string="Ecuadorian Identification Type",
        store=True,
        compute="_compute_l10n_ec_identification_type",
        compute_sudo=True,
    )
    l10n_ec_tax_support_domain_ids = fields.Many2many(
        comodel_name="l10n_ec.tax.support",
        string="Tax Support Domain",
        compute="_compute_l10n_ec_identification_type",
        compute_sudo=True,
    )
    # replace field from Abstract class for change attributes(readonly and states)
    l10n_ec_point_of_emission_id = fields.Many2one(
        comodel_name="l10n_ec.point.of.emission",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    # campo para el punto de emision de retenciones
    # se crea un campo xq el otro es para ventas
    l10n_ec_point_of_emission_withhold_id = fields.Many2one(
        comodel_name="l10n_ec.point.of.emission",
        string="Point of emission",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    l10n_ec_authorization_line_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization.line",
        string="Own Ecuadorian Authorization Line",
    )
    l10n_ec_authorization_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization",
        string="Own Ecuadorian Authorization",
        related="l10n_ec_authorization_line_id.authorization_id",
        store=True,
    )
    l10n_ec_type_emission = fields.Selection(
        string="Type Emission",
        selection=[
            ("electronic", "Electronic"),
            ("pre_printed", "Pre Printed"),
            ("auto_printer", "Auto Printer"),
        ],
        required=False,
        default=False,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    @api.depends(
        "name", "l10n_latam_document_type_id",
    )
    def _compute_l10n_ec_document_number(self):
        recs_with_name = self.filtered(
            lambda x: x.name != "/" and x.company_id.country_id.code == "EC"
        )
        for rec in recs_with_name:
            name = rec.name
            doc_code_prefix = rec.l10n_latam_document_type_id.doc_code_prefix
            if doc_code_prefix and name:
                name = name.split(" ", 1)[-1]
            rec.l10n_ec_document_number = name
        remaining = self - recs_with_name
        remaining.l10n_ec_document_number = False

    l10n_ec_document_number = fields.Char(
        string="Ecuadorian Document Number",
        readonly=True,
        compute="_compute_l10n_ec_document_number",
        store=True,
    )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.partner_id and self.partner_id.l10n_ec_sri_payment_id:
            self.l10n_ec_sri_payment_id = self.partner_id.l10n_ec_sri_payment_id.id
        return res

    @api.model
    def default_get(self, fields):
        values = super(AccountMove, self).default_get(fields)
        type = values.get("type", self.type)
        fields_ec_to_fill = {
            "l10n_ec_point_of_emission_id",
            "l10n_ec_withhold_number",
            "l10n_latam_document_number" "l10n_ec_authorization_line_id",
        }
        if (
            type in ("out_invoice", "out_refund", "in_invoice",)
            and fields_ec_to_fill.intersection(set(fields))
            and self.env.company.country_id.code == "EC"
        ):
            invoice_type = modules_mapping.l10n_ec_get_invoice_type(
                type,
                values.get("l10n_ec_debit_note", self.l10n_ec_debit_note),
                values.get("l10n_ec_liquidation", self.l10n_ec_liquidation),
            )
            if invoice_type in (
                "out_invoice",
                "out_refund",
                "debit_note_out",
                "liquidation",
                "in_invoice",
            ):
                default_printer = (
                    self.env["res.users"]
                    .get_default_point_of_emission(
                        self.env.user.id, raise_exception=True
                    )
                    .get("default_printer_default_id")
                )
                values["l10n_ec_point_of_emission_id"] = default_printer.id
                values["l10n_ec_point_of_emission_withhold_id"] = default_printer.id
                if default_printer:
                    values["l10n_ec_type_emission"] = default_printer.type_emission
                    if invoice_type == "in_invoice":
                        (
                            next_number,
                            auth_line,
                        ) = default_printer.get_next_value_sequence(
                            "withhold_purchase", False, False
                        )
                        if next_number:
                            values["l10n_ec_withhold_number"] = next_number
                        if auth_line:
                            values["l10n_ec_authorization_line_id"] = auth_line.id
                    else:
                        (
                            next_number,
                            auth_line,
                        ) = default_printer.get_next_value_sequence(
                            invoice_type, False, False
                        )
                        if next_number:
                            values["l10n_latam_document_number"] = next_number
                        if auth_line:
                            values["l10n_ec_authorization_line_id"] = auth_line.id
        return values

    def copy_data(self, default=None):
        if not default:
            default = {}
        if self.filtered(lambda x: x.company_id.country_id.code == "EC"):
            inv_type = default.get("type") or self.type
            l10n_ec_debit_note = (
                default.get("l10n_ec_debit_note") or self.l10n_ec_debit_note
            )
            l10n_ec_liquidation = (
                default.get("l10n_ec_liquidation") or self.l10n_ec_liquidation
            )
            invoice_type = modules_mapping.l10n_ec_get_invoice_type(
                inv_type, l10n_ec_debit_note, l10n_ec_liquidation, False
            )
            if self.l10n_ec_point_of_emission_id and invoice_type in (
                "out_invoice",
                "out_refund",
                "liquidation",
                "debit_note_out",
            ):
                (
                    next_number,
                    auth_line,
                ) = self.l10n_ec_point_of_emission_id.get_next_value_sequence(
                    invoice_type, False, False
                )
                default["l10n_latam_document_number"] = next_number
                default["l10n_ec_authorization_line_id"] = auth_line.id
        return super(AccountMove, self).copy_data(default)

    l10n_ec_withhold_number = fields.Char(
        string="Withhold Number",
        required=False,
        readonly=True,
        size=17,
        states={"draft": [("readonly", False)]},
    )

    @api.onchange(
        "type",
        "l10n_ec_debit_note",
        "l10n_ec_liquidation",
        "l10n_ec_point_of_emission_id",
        "invoice_date",
    )
    def _onchange_point_of_emission(self):
        for move in self.filtered(
            lambda x: x.company_id.country_id.code == "EC"
            and x.type in ("out_invoice", "out_refund", "in_invoice")
        ):
            if move.l10n_ec_point_of_emission_id:
                invoice_type = move.l10n_ec_get_invoice_type()
                if invoice_type in (
                    "out_invoice",
                    "out_refund",
                    "debit_note_out",
                    "liquidation",
                    "in_invoice",
                ):
                    if invoice_type == "in_invoice":
                        (
                            next_number,
                            auth_line,
                        ) = move.l10n_ec_point_of_emission_id.get_next_value_sequence(
                            "withhold_purchase", move.invoice_date, False
                        )
                        if next_number:
                            move.l10n_ec_withhold_number = next_number
                        if auth_line:
                            move.l10n_ec_authorization_line_id = auth_line.id
                    else:
                        (
                            next_number,
                            auth_line,
                        ) = move.l10n_ec_point_of_emission_id.get_next_value_sequence(
                            invoice_type, move.invoice_date, False
                        )
                        move.l10n_ec_type_emission = (
                            move.l10n_ec_point_of_emission_id.type_emission
                        )
                        if next_number:
                            move.l10n_latam_document_number = next_number
                        move.l10n_ec_authorization_line_id = auth_line.id

    l10n_ec_withhold_required = fields.Boolean(
        string="Withhold Required",
        compute="_compute_l10n_ec_withhold_required",
        store=True,
    )
    l10n_ec_withhold_date = fields.Date(
        string="Withhold Date", readonly=True, states={"draft": [("readonly", False)]},
    )

    @api.depends(
        "type", "line_ids.tax_ids", "l10n_ec_debit_note", "l10n_ec_liquidation",
    )
    def _compute_l10n_ec_withhold_required(self):
        group_iva_withhold = self.env.ref("l10n_ec_niif.tax_group_iva_withhold")
        group_rent_withhold = self.env.ref("l10n_ec_niif.tax_group_renta_withhold")
        for rec in self:
            withhold_required = False
            if rec.type == "in_invoice":
                withhold_required = any(
                    t.tax_group_id.id in (group_iva_withhold.id, group_rent_withhold.id)
                    for t in rec.line_ids.mapped("tax_ids")
                )
            rec.l10n_ec_withhold_required = withhold_required

    @api.constrains(
        "name",
        "l10n_ec_document_number",
        "company_id",
        "type",
        "l10n_ec_debit_note",
        "l10n_ec_liquidation",
    )
    def _check_l10n_ec_document_number_duplicity(self):
        auth_line_model = self.env["l10n_ec.sri.authorization.line"]
        for move in self.filtered(
            lambda x: x.company_id.country_id.code == "EC"
            and x.l10n_ec_get_invoice_type()
            in ("out_invoice", "out_refund", "debit_note_out", "liquidation")
            and x.l10n_ec_document_number
        ):
            auth_line_model.with_context(
                from_constrain=True
            ).validate_unique_value_document(
                move.l10n_ec_get_invoice_type(),
                move.l10n_ec_document_number,
                move.company_id.id,
                move.id,
            )

    @api.depends(
        "type", "l10n_ec_debit_note", "l10n_ec_liquidation",
    )
    def _compute_l10n_ec_invoice_filter_type_domain(self):
        for move in self:
            if move.is_sale_document(include_receipts=True):
                if not move.l10n_ec_debit_note:
                    move.l10n_ec_invoice_filter_type_domain = "sale"
                else:
                    move.l10n_ec_invoice_filter_type_domain = "debit_note_out"
            elif move.is_purchase_document(include_receipts=True):
                if not move.l10n_ec_debit_note and not move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = "purchase"
                elif move.l10n_ec_debit_note and not move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = "debit_note_in"
                elif not move.l10n_ec_debit_note and move.l10n_ec_liquidation:
                    move.l10n_ec_invoice_filter_type_domain = "liquidation"
                else:
                    move.l10n_ec_invoice_filter_type_domain = "purchase"
            else:
                move.l10n_ec_invoice_filter_type_domain = False

    l10n_ec_invoice_filter_type_domain = fields.Char(
        string="Journal Domain",
        required=False,
        compute="_compute_l10n_ec_invoice_filter_type_domain",
    )

    @api.model
    def _get_default_journal(self):
        journal_model = self.env["account.journal"]
        if self.env.context.get("default_type", False) in (
            "out_receipt",
            "in_receipt",
        ):
            journal = journal_model.search(
                [
                    (
                        "company_id",
                        "=",
                        self._context.get("default_company_id", self.env.company.id),
                    ),
                    (
                        "type",
                        "=",
                        self.env.context.get("default_type", False) == "out_receipt"
                        and "sale"
                        or "purchase",
                    ),
                    ("l10n_latam_use_documents", "=", False),
                ],
                limit=1,
            )
            if journal:
                return super(
                    AccountMove, self.with_context(default_journal_id=journal.id)
                )._get_default_journal()
        if self.env.context.get("default_type", False) in (
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
        ):
            invoice_type = modules_mapping.l10n_ec_get_invoice_type(
                self.env.context.get("default_type", False),
                self.env.context.get("default_l10n_ec_debit_note", False),
                self.env.context.get("default_l10n_ec_liquidation", False),
            )
            if invoice_type in ("debit_note_in", "debit_note_out", "liquidation"):
                journal = journal_model.search(
                    [
                        (
                            "company_id",
                            "=",
                            self._context.get(
                                "default_company_id", self.env.company.id
                            ),
                        ),
                        ("l10n_ec_extended_type", "=", invoice_type),
                    ],
                    limit=1,
                )
                if journal:
                    return super(
                        AccountMove, self.with_context(default_journal_id=journal.id)
                    )._get_default_journal()
        return super(AccountMove, self)._get_default_journal()

    journal_id = fields.Many2one(default=_get_default_journal)

    @api.onchange(
        "l10n_ec_original_invoice_id", "invoice_date",
    )
    def onchange_l10n_ec_original_invoice(self):
        line_model = self.env["account.move.line"].with_context(
            check_move_validity=False
        )
        if self.l10n_ec_original_invoice_id:
            lines = line_model.browse()
            default_move = {
                "ref": _("Reversal"),
                "date": self.invoice_date or fields.Date.context_today(self),
                "invoice_date": self.invoice_date or fields.Date.context_today(self),
                "journal_id": self.journal_id and self.journal_id.id,
                "invoice_payment_term_id": None,
            }
            move_vals = self.l10n_ec_original_invoice_id._reverse_move_vals(
                default_move
            )
            for _a, _b, line_data in move_vals.get("line_ids"):
                if line_data.get("exclude_from_invoice_tab", False):
                    continue
                if "move_id" in line_data:
                    line_data.pop("move_id")
                if "date" not in line_data:
                    line_data.update(
                        {"date": self.invoice_date or fields.Date.context_today(self),}
                    )
                new_line = line_model.new(line_data)
                if new_line.currency_id:
                    new_line._onchange_currency()
                lines += new_line
            self.line_ids = lines
            self._recompute_dynamic_lines(recompute_all_taxes=True)

    @api.depends("commercial_partner_id")
    def _compute_l10n_ec_consumidor_final(self):
        consumidor_final = self.env.ref("l10n_ec_niif.consumidor_final")
        for move in self:
            if move.commercial_partner_id.id == consumidor_final.id:
                move.l10n_ec_consumidor_final = True
            else:
                move.l10n_ec_consumidor_final = False

    l10n_ec_consumidor_final = fields.Boolean(
        string="Consumidor Final", compute="_compute_l10n_ec_consumidor_final"
    )

    def _check_document_values_for_ecuador(self):
        # TODO: se deberia agregar un campo en el grupo de impuesto para diferenciarlos(l10n_ec_type_ec)
        supplier_authorization_model = self.env["l10n_ec.sri.authorization.supplier"]
        withhold_iva_group = self.env.ref("l10n_ec_niif.tax_group_iva_withhold")
        withhold_rent_group = self.env.ref("l10n_ec_niif.tax_group_renta_withhold")
        iva_group = self.env.ref("l10n_ec_niif.tax_group_iva")
        error_list = []
        # validaciones para consumidor final
        # * no permitir factura de ventas mayor a un monto configurado(200 USD por defecto)
        # * no permitir emitir Nota de credito ni factura de proveedor
        if self.l10n_ec_consumidor_final:
            if (
                self.type == "out_invoice"
                and float_compare(
                    self.amount_total,
                    self.company_id.l10n_ec_consumidor_final_limit,
                    precision_digits=2,
                )
                == 1
            ):
                raise UserError(
                    _(
                        "You can't make invoice where amount total %s "
                        "is bigger than %s for final customer"
                    )
                    % (
                        self.amount_total,
                        self.company_id.l10n_ec_consumidor_final_limit,
                    )
                )
            if self.type in ("in_invoice", "in_refund", "out_refund"):
                raise UserError(
                    _(
                        "You can't make bill or refund to final customer on ecuadorian company"
                    )
                )
        if self.l10n_ec_invoice_type in ("in_invoice", "in_refund", "debit_note_in"):
            supplier_authorization_model.validate_unique_document_partner(
                self.l10n_ec_invoice_type,
                self.l10n_latam_document_number,
                self.partner_id.id,
                self.id,
            )
            if self.l10n_ec_type_emission in ("pre_printed", "auto_printer"):
                if self.l10n_ec_supplier_authorization_id:
                    supplier_authorization_model.check_number_document(
                        self.l10n_ec_invoice_type,
                        self.l10n_latam_document_number,
                        self.l10n_ec_supplier_authorization_id,
                        self.invoice_date,
                        self.id,
                        self.commercial_partner_id.l10n_ec_foreign,
                    )
                else:
                    raise UserError(
                        _(
                            "You must enter the authorization of the third party to continue"
                        )
                    )
        # validaciones en facturas de proveedor para emitir retenciones
        # * tener 1 impuesto de retencion IVA y 1 impuesto de retencion RENTA
        # * no permitir retener IVA si no hay impuesto de IVA(evitar IVA 0)
        if self.type == "in_invoice":
            for line in self.invoice_line_ids:
                iva_taxes = line.tax_ids.filtered(
                    lambda x: x.tax_group_id.id == iva_group.id and x.amount > 0
                )
                iva_0_taxes = line.tax_ids.filtered(
                    lambda x: x.tax_group_id.id == iva_group.id and x.amount == 0
                )
                withhold_iva_taxes = line.tax_ids.filtered(
                    lambda x: x.tax_group_id.id == withhold_iva_group.id
                    and x.amount > 0
                )
                rent_withhold_taxes = line.tax_ids.filtered(
                    lambda x: x.tax_group_id.id == withhold_rent_group.id
                )
                if self.partner_id.country_id.code == "EC":
                    if len(rent_withhold_taxes) == 0:
                        error_list.append(
                            _("You must apply at least one income withholding tax")
                        )
                    if len(iva_taxes) == 0 and len(iva_0_taxes) == 0:
                        error_list.append(_("You must apply at least one VAT tax"))
                if len(iva_taxes) >= 1 and len(iva_0_taxes) >= 1:
                    error_list.append(
                        _("Cannot apply VAT zero rate with another VAT rate")
                    )
                if len(iva_taxes) > 1:
                    error_list.append(
                        _("You cannot have more than one VAT tax %s")
                        % (" / ".join(t.description or t.name for t in iva_taxes))
                    )
                if len(iva_0_taxes) > 1:
                    error_list.append(
                        _("You cannot have more than one VAT 0 tax %s")
                        % (" / ".join(t.description or t.name for t in iva_0_taxes))
                    )
                if len(withhold_iva_taxes) > 1:
                    error_list.append(
                        _("You cannot have more than one VAT Withholding tax %s")
                        % (
                            " / ".join(
                                t.description or t.name for t in withhold_iva_taxes
                            )
                        )
                    )
                if len(rent_withhold_taxes) > 1:
                    error_list.append(
                        _("You cannot have more than one Rent Withholding tax %s")
                        % (
                            " / ".join(
                                t.description or t.name for t in rent_withhold_taxes
                            )
                        )
                    )
                if len(iva_taxes) == 0 and len(withhold_iva_taxes) > 0:
                    error_list.append(
                        _(
                            "You cannot apply VAT withholding without an assigned VAT tax %s"
                        )
                        % (
                            " / ".join(
                                t.description or t.name for t in withhold_iva_taxes
                            )
                        )
                    )
        if error_list:
            raise UserError("\n".join(error_list))
        return True

    def _prepare_withhold_values(self):
        """
        :return: dict with values for create a new withhold
        """
        withhold_values = {
            "company_id": self.company_id.id,
            "number": self.l10n_ec_withhold_number,
            "issue_date": self.l10n_ec_withhold_date,
            "partner_id": self.partner_id.id,
            "invoice_id": self.id,
            "type": "purchase",
            "document_type": self.l10n_ec_type_emission,
            "point_of_emission_id": self.l10n_ec_point_of_emission_withhold_id.id,
            "authorization_line_id": self.l10n_ec_authorization_line_id.id,
            "state": "draft",
        }
        return withhold_values

    def _prepare_withhold_lines_values(self, withhold):
        """
        Compute withhold lines based on taxes groups for withhold IVA and RENTA
        :param withhold: recordset(l10n_ec.withhold) to create lines
        :return: list(dict) with values for create withhold lines
        """
        percent_model = self.env["l10n_ec.withhold.line.percent"]
        withhold_iva_group = self.env.ref("l10n_ec_niif.tax_group_iva_withhold")
        withhold_rent_group = self.env.ref("l10n_ec_niif.tax_group_renta_withhold")
        tax_data = {}
        for line in self.invoice_line_ids:
            for tax in line.tax_ids:
                if tax.tax_group_id.id in (
                    withhold_iva_group.id,
                    withhold_rent_group.id,
                ):
                    base_tag_id = tax.invoice_repartition_line_ids.filtered(
                        lambda x: x.repartition_type == "base"
                    ).mapped("tag_ids")
                    tax_tag_id = tax.invoice_repartition_line_ids.filtered(
                        lambda x: x.repartition_type == "tax"
                    ).mapped("tag_ids")
                    tax_type = "rent"
                    percent = abs(tax.amount)
                    if tax.tax_group_id.id == withhold_iva_group.id:
                        tax_type = "iva"
                        percent = abs(
                            tax.invoice_repartition_line_ids.filtered(
                                lambda x: x.repartition_type == "tax"
                            ).factor_percent
                        )
                    tax_data.setdefault(
                        tax,
                        {
                            "withhold_id": withhold.id,
                            "invoice_id": self.id,
                            "tax_id": tax.id,
                            "base_tag_id": base_tag_id and base_tag_id.ids[0] or False,
                            "tax_tag_id": tax_tag_id and tax_tag_id.ids[0] or False,
                            "type": tax_type,
                            "base_amount": 0.0,
                            "tax_amount": 0.0,
                            "base_amount_currency": 0.0,
                            "tax_amount_currency": 0.0,
                            "percent_id": percent_model._get_percent(
                                percent, tax_type
                            ).id,
                        },
                    )
        for tax in tax_data.keys():
            base_amount = 0
            tax_amount = 0
            base_tag_id = tax_data[tax].get("base_tag_id")
            tax_tag_id = tax_data[tax].get("tax_tag_id")
            for line in self.line_ids:
                for tag in line.tag_ids.filtered(
                    lambda x: x.id in (base_tag_id, tax_tag_id)
                ):
                    tag_amount = line.balance
                    if tag.id == base_tag_id:
                        base_amount = abs(tag_amount)
                        tax_data[tax]["base_amount"] += base_amount
                        tax_data[tax][
                            "base_amount_currency"
                        ] += self.currency_id.compute(
                            base_amount, self.company_id.currency_id
                        )
                    if tag.id == tax_tag_id:
                        tax_amount = abs(tag_amount)
                        tax_data[tax]["tax_amount"] += tax_amount
                        tax_data[tax][
                            "tax_amount_currency"
                        ] += self.currency_id.compute(
                            tax_amount, self.company_id.currency_id
                        )
        for tax, tax_vals in tax_data.items():
            if tax.tax_group_id.id == withhold_iva_group.id:
                tax_vals["base_amount"] = tax_vals["tax_amount"] / (
                    percent_model.browse(tax_vals["percent_id"]).percent / 100.0
                )
                tax_vals["base_amount_currency"] = self.currency_id.compute(
                    tax_vals["base_amount"], self.company_id.currency_id
                )
        return tax_data.values()

    def action_post(self):
        withhold_model = self.env["l10n_ec.withhold"]
        withhold_line_model = self.env["l10n_ec.withhold.line"]
        for move in self:
            if move.company_id.country_id.code == "EC":
                move._check_document_values_for_ecuador()
                # proceso de retenciones en compra
                if move.type == "in_invoice":
                    if move.l10n_ec_withhold_required:
                        current_withhold = withhold_model.create(
                            move._prepare_withhold_values()
                        )
                        tax_data = move._prepare_withhold_lines_values(current_withhold)
                        withhold_line_model.create(tax_data)

                        current_withhold.action_done()
                # proceso de facturacion electronica
                if move.is_invoice():
                    move.l10n_ec_action_create_xml_data()
        return super(AccountMove, self).action_post()

    def _reverse_move_vals(self, default_values, cancel=True):
        # pasar la referencia al campo que se usa en localizacion ecuatoriana
        # TODO: revisar si realmente es necesario agregar un nuevo campo o se podria usar el de Odoo base
        default_values["l10n_ec_original_invoice_id"] = self.id
        return super(AccountMove, self)._reverse_move_vals(
            default_values, cancel=cancel
        )

    def button_draft(self):
        for move in self:
            if move.is_purchase_document() and move.l10n_ec_withhold_ids:
                move.l10n_ec_withhold_ids.action_cancel()
                move.l10n_ec_withhold_ids.with_context(
                    cancel_from_invoice=True
                ).unlink()
        return super(AccountMove, self).button_draft()

    def unlink(self):
        if self.env.context.get("skip_recurtion", False):
            return super(AccountMove, self).unlink()
        for move in self:
            if move.company_id.country_id.code == "EC":
                if move.type in (
                    "out_invoice",
                    "out_refund",
                    "in_invoice",
                    "in_refund",
                ):
                    if move.state != "draft":
                        raise UserError(_("You only delete invoices in draft state"))
                    else:
                        move.with_context(
                            skip_recurtion=True, force_delete=True
                        ).unlink()

    @api.depends(
        "line_ids.price_subtotal",
        "line_ids.tax_base_amount",
        "line_ids.tax_line_id",
        "partner_id",
        "currency_id",
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
                iva_group = self.env.ref("l10n_ec_niif.tax_group_iva")
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
                l10n_ec_base_iva_0, move.company_currency_id, move.company_id, move_date
            )
            move.l10n_ec_base_iva_currency = move.currency_id._convert(
                l10n_ec_base_iva, move.company_currency_id, move.company_id, move_date
            )
            move.l10n_ec_iva_currency = move.currency_id._convert(
                l10n_ec_iva, move.company_currency_id, move.company_id, move_date
            )
            move.l10n_ec_discount_total_currency = move.currency_id._convert(
                l10n_ec_discount_total,
                move.company_currency_id,
                move.company_id,
                move_date,
            )

    l10n_ec_withhold_id = fields.Many2one(
        comodel_name="l10n_ec.withhold", string="Withhold", required=False
    )

    l10n_ec_withhold_line_ids = fields.One2many(
        comodel_name="l10n_ec.withhold.line",
        inverse_name="invoice_id",
        string="Withhold Lines",
        required=False,
    )

    l10n_ec_withhold_ids = fields.Many2many(
        comodel_name="l10n_ec.withhold",
        string="Withhold",
        compute="_compute_l10n_ec_withhold_ids",
    )
    l10n_ec_withhold_count = fields.Integer(
        string="Withhold Count", compute="_compute_l10n_ec_withhold_ids", store=False
    )

    @api.depends("l10n_ec_withhold_line_ids.withhold_id",)
    def _compute_l10n_ec_withhold_ids(self):
        for rec in self:
            l10n_ec_withhold_ids = rec.l10n_ec_withhold_line_ids.mapped(
                "withhold_id"
            ).ids
            if not l10n_ec_withhold_ids:
                l10n_ec_withhold_ids = rec.l10n_ec_withhold_ids.search(
                    [("invoice_id", "=", rec.id)]
                ).ids
            rec.l10n_ec_withhold_ids = l10n_ec_withhold_ids
            rec.l10n_ec_withhold_count = len(l10n_ec_withhold_ids)

    def action_show_l10n_ec_withholds(self):
        self.ensure_one()
        action = self.env.ref(
            "l10n_ec_niif.l10n_ec_withhold_purchase_act_window"
        ).read()[0]

        withholds = self.mapped("l10n_ec_withhold_ids")
        if len(withholds) > 1:
            action["domain"] = [("id", "in", withholds.ids)]
        elif withholds:
            form_view = [
                (self.env.ref("l10n_ec_niif.l10n_ec_withhold_form_view").id, "form")
            ]
            if "views" in action:
                action["views"] = form_view + [
                    (state, view) for state, view in action["views"] if view != "form"
                ]
            else:
                action["views"] = form_view
            action["res_id"] = withholds.id
        action["context"] = dict(
            self._context,
            default_partner_id=self.partner_id.id,
            default_invoice_id=self.id,
        )
        return action

    def create_withhold_customer(self):
        self.ensure_one()
        action = self.env.ref("l10n_ec_niif.l10n_ec_withhold_sales_act_window").read()[
            0
        ]
        action["views"] = [
            (self.env.ref("l10n_ec_niif.l10n_ec_withhold_form_view").id, "form")
        ]
        ctx = safe_eval(action["context"])
        ctx.update(
            {
                "default_partner_id": self.partner_id.id,
                "default_invoice_id": self.id,
                "default_type": "sale",
                "default_issue_date": self.invoice_date,
                "default_document_type": self.l10n_ec_type_emission,
                "default_l10n_ec_is_create_from_invoice": True,
            }
        )
        action["context"] = ctx
        return action

    l10n_ec_start_date = fields.Date(
        "Start Date", related="l10n_ec_authorization_id.start_date"
    )
    l10n_ec_expiration_date = fields.Date(
        "Expiration Date", related="l10n_ec_authorization_id.expiration_date"
    )

    @api.constrains("l10n_ec_start_date", "l10n_ec_expiration_date", "invoice_date")
    def _check_outside(self):
        if any(
            outside_start
            for outside_start in self
            if outside_start.invoice_date
            and outside_start.l10n_ec_start_date
            and outside_start.invoice_date < outside_start.l10n_ec_start_date
        ):
            raise UserError(_("Invoice date outside defined date range"))
        if any(
            outside_expiration
            for outside_expiration in self
            if outside_expiration.invoice_date
            and outside_expiration.l10n_ec_expiration_date
            and outside_expiration.invoice_date
            > outside_expiration.l10n_ec_expiration_date
        ):
            raise UserError(_("Invoice date outside defined date range2"))

    def l10n_ec_get_invoice_type(self):
        self.ensure_one()
        return modules_mapping.l10n_ec_get_invoice_type(
            self.type, self.l10n_ec_debit_note, self.l10n_ec_liquidation, False
        )

    def l10n_ec_validate_fields_required_fe(self):
        message_list = []
        if not self.company_id.partner_id.vat:
            message_list.append(
                f"Debe asignar el RUC en la Compañia: {self.company_id.partner_id.name}, por favor verifique."
            )
        if not self.company_id.partner_id.street:
            message_list.append(
                f"Debe asignar la direccion en la Compañia: {self.company_id.partner_id.name}, por favor verifique."
            )
        if not self.commercial_partner_id.vat:
            message_list.append(
                f"Debe asignar el RUC en la Empresa: {self.commercial_partner_id.name}, por favor verifique."
            )
        if not self.commercial_partner_id.street:
            message_list.append(
                f"Debe asignar la direccion en la Empresa: {self.commercial_partner_id.name}, por favor verifique."
            )
        if not self.l10n_ec_sri_payment_id:
            message_list.append(
                f"Debe asignar la forma de pago del SRI en el documento: {self.display_name}, por favor verifique."
            )
        # validaciones para reembolso en liquidacion de compras
        if self.l10n_ec_liquidation and self.l10n_ec_refund_ids:
            for refund in self.l10n_ec_refund_ids:
                if not refund.partner_id.commercial_partner_id.vat:
                    message_list.append(
                        f"En Reembolsos debe asignar el RUC en la Empresa: {refund.partner_id.commercial_partner_id.name}, por favor verifique."
                    )
                if refund.currency_id.is_zero(refund.total_invoice):
                    message_list.append(
                        "El total del reembolso debe ser mayor a cero, por favor verifique."
                    )
        if self.type == "out_refund":
            if (
                not self.l10n_ec_original_invoice_id
                and not self.l10n_ec_legacy_document_number
            ):
                message_list.append(
                    f"La Nota de Credito: {self.display_name} no esta asociada "
                    f"a ningun documento que modifique tributariamente, por favor verifique"
                )
            # validar que la factura este autorizada electronicamente
            if (
                self.l10n_ec_original_invoice_id
                and not self.l10n_ec_original_invoice_id.l10n_ec_xml_data_id
            ):
                message_list.append(
                    f"No puede generar una Nota de credito, "
                    f"cuya factura rectificativa: {self.l10n_ec_original_invoice_id.display_name} "
                    f"no esta autorizada electronicamente!"
                )
        return message_list

    def l10n_ec_action_create_xml_data(self):
        xml_model = self.env["sri.xml.data"]
        xml_recs = self.env["sri.xml.data"].browse()
        # si por context me pasan que no cree la parte electronica
        if self.env.context.get("no_create_electronic", False):
            return True
        # Si ya se encuentra autorizado, no hacer nuevamente el proceso de generacion del xml
        for invoice in self.filtered(lambda x: not x.l10n_ec_xml_data_id):
            invoice_type = invoice.l10n_ec_get_invoice_type()
            if invoice.type == "in_invoice":
                for retention in invoice.l10n_ec_withhold_ids:
                    if retention.point_of_emission_id.type_emission != "electronic":
                        continue
                    if not retention.no_number:
                        # si el documento esta habilitado, hacer el proceso electronico
                        if xml_model._is_document_authorized("withhold_purchase"):
                            company = retention.company_id or self.env.company
                            sri_xml_vals = retention._prepare_l10n_ec_sri_xml_values(
                                company
                            )
                            sri_xml_vals["withhold_id"] = retention.id
                            new_xml_rec = xml_model.create(sri_xml_vals)
                            xml_recs += new_xml_rec
                            retention._l10n_ec_add_followers_to_electronic_documents()
            # si el documento esta habilitado, hacer el proceso electronico
            if (
                invoice.l10n_ec_point_of_emission_id.type_emission == "electronic"
                and xml_model._is_document_authorized(invoice_type)
            ):
                message_list = invoice.l10n_ec_validate_fields_required_fe()
                if message_list:
                    raise UserError("\n".join(message_list))
                # asegurarse que el documento tenga fecha
                # recien en la llamada super se haria esa asignacion
                # pero necesitamos la fecha para crear el xml
                # (codigo copiado del metodo post)
                # *********************************************************************************************
                if not invoice.invoice_date and invoice.is_invoice(
                    include_receipts=True
                ):
                    invoice.invoice_date = fields.Date.context_today(invoice)
                    invoice.with_context(
                        check_move_validity=False
                    )._onchange_invoice_date()
                # *********************************************************************************************
                company = invoice.company_id or self.env.company
                sri_xml_vals = invoice._prepare_l10n_ec_sri_xml_values(company)
                # factura
                if invoice_type == "out_invoice":
                    sri_xml_vals["invoice_out_id"] = invoice.id
                # nota de debito
                elif invoice_type == "debit_note_out":
                    sri_xml_vals["debit_note_out_id"] = invoice.id
                # nota de credito
                elif invoice_type == "out_refund":
                    sri_xml_vals["credit_note_out_id"] = invoice.id
                # liquidacion de compas
                elif invoice_type == "liquidation":
                    sri_xml_vals["liquidation_id"] = invoice.id
                new_xml_rec = xml_model.create(sri_xml_vals)
                xml_recs += new_xml_rec
                invoice._l10n_ec_add_followers_to_electronic_documents()
        if xml_recs:
            xml_recs.process_document_electronic()
        return True

    def _l10n_ec_add_followers_to_electronic_documents(self):
        partners = self.env["res.partner"].browse()
        invoice_type = self.l10n_ec_get_invoice_type()
        boolean_field_name = ""
        if invoice_type == "out_invoice":
            boolean_field_name = "l10n_ec_email_out_invoice"
        if invoice_type == "out_refund":
            boolean_field_name = "l10n_ec_email_out_refund"
        if invoice_type == "debit_note_out":
            boolean_field_name = "l10n_ec_email_debit_note_out"
        if invoice_type == "liquidation":
            boolean_field_name = "l10n_ec_email_liquidation"
        if boolean_field_name:
            if (
                self.commercial_partner_id[boolean_field_name]
                and self.commercial_partner_id not in self.message_partner_ids
            ):
                partners |= self.commercial_partner_id
            for contact in self.commercial_partner_id.child_ids:
                if (
                    contact[boolean_field_name]
                    and contact not in self.message_partner_ids
                ):
                    partners |= contact
        if partners:
            self.message_subscribe(partners.ids)
        return True

    @api.model
    def l10n_ec_get_total_impuestos(
        self,
        parent_node,
        codigo,
        codigo_porcentaje,
        base,
        valor,
        tag_name="totalImpuesto",
        tarifa=-1,
        refund=False,
        liquidation=False,
        decimales=2,
    ):
        util_model = self.env["l10n_ec.utils"]
        tag = SubElement(parent_node, tag_name)
        SubElement(tag, "codigo").text = codigo
        SubElement(tag, "codigoPorcentaje").text = codigo_porcentaje
        if liquidation:
            if refund:
                if tarifa != -1:
                    SubElement(tag, "tarifa").text = util_model.formato_numero(
                        tarifa, 0
                    )
                SubElement(
                    tag, "baseImponibleReembolso"
                ).text = util_model.formato_numero(base, decimales)
                SubElement(tag, "impuestoReembolso").text = util_model.formato_numero(
                    valor, decimales
                )
            else:
                SubElement(tag, "baseImponible").text = util_model.formato_numero(
                    base, decimales
                )
                if tarifa != -1:
                    SubElement(tag, "tarifa").text = util_model.formato_numero(
                        tarifa, 0
                    )
                SubElement(tag, "valor").text = util_model.formato_numero(
                    valor, decimales
                )
        else:
            if tarifa != -1:
                SubElement(tag, "tarifa").text = util_model.formato_numero(tarifa, 0)
            if refund:
                SubElement(
                    tag, "baseImponibleReembolso"
                ).text = util_model.formato_numero(base, decimales)
                SubElement(tag, "impuestoReembolso").text = util_model.formato_numero(
                    valor, decimales
                )
            else:
                SubElement(tag, "baseImponible").text = util_model.formato_numero(
                    base, decimales
                )
                SubElement(tag, "valor").text = util_model.formato_numero(
                    valor, decimales
                )
        return tag

    @api.model
    def l10n_ec_get_motives(self, parent_node, razon="", valor=0, tag_name="motivo"):
        util_model = self.env["l10n_ec.utils"]
        tag = SubElement(parent_node, tag_name)
        SubElement(tag, "razon").text = razon
        SubElement(tag, "valor").text = util_model.formato_numero(valor, 2)
        return tag

    def l10n_ec_get_payment_data(self):
        payment_data = []
        foreign_currency = (
            self.currency_id
            if self.currency_id != self.company_id.currency_id
            else False
        )
        pay_term_line_ids = self.line_ids.filtered(
            lambda line: line.account_id.user_type_id.type in ("receivable", "payable")
        )
        partials = pay_term_line_ids.mapped(
            "matched_debit_ids"
        ) + pay_term_line_ids.mapped("matched_credit_ids")
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            counterpart_line = counterpart_lines.filtered(
                lambda line: line not in self.line_ids
            )
            if not counterpart_line.payment_id.l10n_ec_sri_payment_id:
                continue
            if foreign_currency and partial.currency_id == foreign_currency:
                amount = partial.amount_currency
            else:
                amount = partial.company_currency_id._convert(
                    partial.amount, self.currency_id, self.company_id, self.date
                )
            if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                continue
            payment_vals = {
                "name": counterpart_line.payment_id.l10n_ec_sri_payment_id.name,
                "formaPago": counterpart_line.payment_id.l10n_ec_sri_payment_id.code,
                "total": amount,
            }
            if (
                self.invoice_payment_term_id
                and self.invoice_payment_term_id.l10n_ec_sri_type == "credito"
                and self.l10n_ec_credit_days > 0
            ):
                payment_vals.update(
                    {"plazo": self.l10n_ec_credit_days, "unidadTiempo": "dias",}
                )
            payment_data.append(payment_vals)
        if not payment_data:
            l10n_ec_sri_payment = self.l10n_ec_sri_payment_id
            if not l10n_ec_sri_payment:
                l10n_ec_sri_payment = self.commercial_partner_id.l10n_ec_sri_payment_id
            if not l10n_ec_sri_payment:
                l10n_ec_sri_payment = self.company_id.l10n_ec_sri_payment_id
            if not l10n_ec_sri_payment:
                raise UserError(
                    _(
                        "Debe configurar la forma de pago por defecto esto lo encuentra en Contabilidad / SRI / Configuración"
                    )
                )
            payment_vals = {
                "name": l10n_ec_sri_payment.name,
                "formaPago": l10n_ec_sri_payment.code,
                "total": self.amount_total,
            }
            if (
                self.invoice_payment_term_id
                and self.invoice_payment_term_id.l10n_ec_sri_type == "credito"
                and self.l10n_ec_credit_days > 0
            ):
                payment_vals.update(
                    {"plazo": self.l10n_ec_credit_days, "unidadTiempo": "dias",}
                )
            payment_data.append(payment_vals)
        return payment_data

    def l10n_ec_get_tarifa_iva(self):
        tarifa_iva = 0
        iva_group = self.env.ref("l10n_ec_niif.tax_group_iva")
        for line in self.line_ids:
            if (
                line.tax_line_id.tax_group_id.id == iva_group.id
                and line.tax_line_id.amount > 0
            ):
                tarifa_iva = line.tax_line_id.amount
        return tarifa_iva

    def l10n_ec_get_document_code_sri(self):
        invoice_type = self.l10n_ec_get_invoice_type()
        # factura de venta es codigo 18, pero aca debe pasarse codigo 01
        # los demas documentos tomar del tipo de documento(l10n_latam_document_type_id)
        if invoice_type == "out_invoice":
            document_code_sri = "01"
        else:
            document_code_sri = self.l10n_latam_document_type_id.code
        return document_code_sri

    def l10n_ec_get_document_number(self):
        # esta funcion debe devolver el numero de documento
        return self.l10n_latam_document_number

    def l10n_ec_get_document_date(self):
        # esta funcion debe devolver la fecha de emision del documento
        return self.invoice_date

    def l10n_ec_get_document_string(self):
        return self.l10n_latam_document_type_id.report_name

    def l10n_ec_get_document_version_xml(self):
        # esta funcion debe devolver la version del xml que se debe usar
        company = self.company_id or self.env.company
        invoice_type = self.l10n_ec_get_invoice_type()
        document_type = modules_mapping.get_document_type(invoice_type)
        return company[f"l10n_ec_{document_type}_version_xml_id"]

    def l10n_ec_get_document_filename_xml(self):
        # esta funcion debe devolver el nombre del archivo xml sin la extension
        # algo como: id, prefijo, secuencial
        return f"{self.id}_{self.l10n_latam_document_type_id.doc_code_prefix}_{self.l10n_ec_get_document_number()}"

    def l10n_ec_action_generate_xml_data(self, node_root):
        invoice_type = self.l10n_ec_get_invoice_type()
        if invoice_type == "out_invoice":
            self.l10n_ec_get_info_factura(node_root)
        # nota de credito
        elif invoice_type == "out_refund":
            self.l10n_ec_get_info_credit_note(node_root)
        # nota de debito
        elif invoice_type == "debit_note_out":
            self.l10n_ec_get_info_debit_note(node_root)
        # liquidacion de compras
        elif invoice_type == "liquidation":
            self.l10n_ec_get_info_liquidation(node_root)
        return True

    def l10n_ec_get_info_factura(self, node):
        util_model = self.env["l10n_ec.utils"]
        company = self.company_id or self.env.company
        currency = company.currency_id
        precision_get = self.env["decimal.precision"].precision_get
        digits_precision_product = precision_get("Product Price")
        digits_precision_qty = precision_get("Product Unit of Measure")
        digits_precision_discount = precision_get("Discount")
        infoFactura = SubElement(node, "infoFactura")
        fecha_factura = self.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoFactura, "fechaEmision").text = fecha_factura
        address = company.partner_id.street
        SubElement(infoFactura, "dirEstablecimiento").text = util_model._clean_str(
            address
        )[:300]
        if self.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = self.l10n_ec_identification_type_id.code
        elif self.commercial_partner_id:
            tipoIdentificacionComprador = (
                self.commercial_partner_id.l10n_ec_get_sale_identification_partner()
            )
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = "07"
        numero_contribuyente_especial = company.get_contribuyente_data(
            self.invoice_date
        )
        if numero_contribuyente_especial:
            SubElement(
                infoFactura, "contribuyenteEspecial"
            ).text = numero_contribuyente_especial
        SubElement(
            infoFactura, "obligadoContabilidad"
        ).text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id
        )
        SubElement(
            infoFactura, "tipoIdentificacionComprador"
        ).text = tipoIdentificacionComprador
        # if self.remision_id:
        #     SubElement(infoFactura, "guiaRemision").text = self.remision_id.document_number
        SubElement(infoFactura, "razonSocialComprador").text = util_model._clean_str(
            self.commercial_partner_id.name[:300]
        )
        SubElement(
            infoFactura, "identificacionComprador"
        ).text = self.commercial_partner_id.vat
        SubElement(infoFactura, "direccionComprador").text = util_model._clean_str(
            self.commercial_partner_id.street
        )[:300]

        SubElement(infoFactura, "totalSinImpuestos").text = util_model.formato_numero(
            self.amount_untaxed, currency.decimal_places
        )
        SubElement(infoFactura, "totalDescuento").text = util_model.formato_numero(
            self.l10n_ec_discount_total, currency.decimal_places
        )
        # Definicion de Impuestos
        totalConImpuestos = SubElement(infoFactura, "totalConImpuestos")
        if self.l10n_ec_base_iva_0 != 0:
            self.l10n_ec_get_total_impuestos(
                totalConImpuestos,
                "2",
                "0",
                self.l10n_ec_base_iva_0,
                0.0,
                decimales=currency.decimal_places,
            )
        if self.l10n_ec_base_iva != 0:
            self.l10n_ec_get_total_impuestos(
                totalConImpuestos,
                "2",
                "2",
                self.l10n_ec_base_iva,
                self.l10n_ec_iva,
                decimales=currency.decimal_places,
            )
        # if self.base_no_iva != 0:
        #     self.l10n_ec_get_total_impuestos(totalConImpuestos, '2', '6', self.base_no_iva, 0.0,
        #                              decimales=currency.decimal_places)
        # SubElement(infoFactura, "propina").text = util_model.formato_numero(self.propina or 0,
        #                                                                         currency.decimal_places)
        SubElement(infoFactura, "importeTotal").text = util_model.formato_numero(
            self.amount_total, currency.decimal_places
        )
        SubElement(infoFactura, "moneda").text = (
            self.company_id.currency_id.name or "DOLAR"
        )
        # Procesamiento de los pagos
        payments_data = self.l10n_ec_get_payment_data()
        pagos = SubElement(infoFactura, "pagos")
        for payment_data in payments_data:
            pago = SubElement(pagos, "pago")
            SubElement(pago, "formaPago").text = payment_data["formaPago"]
            SubElement(pago, "total").text = util_model.formato_numero(
                payment_data["total"]
            )
            if payment_data.get("plazo"):
                SubElement(pago, "plazo").text = util_model.formato_numero(
                    payment_data.get("plazo"), 0
                )
                SubElement(pago, "unidadTiempo").text = (
                    payment_data.get("unidadTiempo") or "dias"
                )
        # Lineas de Factura
        detalles = SubElement(node, "detalles")
        for line in self.invoice_line_ids.filtered(lambda x: not x.display_type):
            discount = round(
                ((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2
            )
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            if currency.is_zero(subtotal):
                continue
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoPrincipal").text = util_model._clean_str(
                line.product_id
                and line.product_id.default_code
                and line.product_id.default_code[:25]
                or "N/A"
            )
            #             SubElement(detalle,"codigoAdicional").text = util_model._clean_str(line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300]
            )
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(
                line.quantity, digits_precision_qty
            )
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(
                line.price_unit, digits_precision_product
            )
            SubElement(detalle, "descuento").text = util_model.formato_numero(
                discount or 0.0, digits_precision_discount
            )
            SubElement(
                detalle, "precioTotalSinImpuesto"
            ).text = util_model.formato_numero(subtotal, currency.decimal_places)
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "0",
                    line.l10n_ec_base_iva_0,
                    0.0,
                    "impuesto",
                    0,
                    decimales=currency.decimal_places,
                )
            if line.l10n_ec_base_iva != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "2",
                    line.l10n_ec_base_iva,
                    line.l10n_ec_iva,
                    "impuesto",
                    12,
                    decimales=currency.decimal_places,
                )
            # if line.base_no_iva != 0:
            #     self.l10n_ec_get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0,
            #                              decimales=currency.decimal_places)
        # Las retenciones solo aplican para el esquema de gasolineras
        # retenciones = SubElement(node,"retenciones")
        self.l10n_ec_add_info_adicional(node)
        return node

    def l10n_ec_get_info_credit_note(self, node):
        util_model = self.env["l10n_ec.utils"]
        company = self.company_id or self.env.company
        currency = company.currency_id
        precision_get = self.env["decimal.precision"].precision_get
        digits_precision_product = precision_get("Product Price")
        digits_precision_qty = precision_get("Product Unit of Measure")
        digits_precision_discount = precision_get("Discount")
        infoNotaCredito = SubElement(node, "infoNotaCredito")
        fecha_factura = self.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoNotaCredito, "fechaEmision").text = fecha_factura
        address = company.partner_id.street
        SubElement(infoNotaCredito, "dirEstablecimiento").text = util_model._clean_str(
            address and address[:300] or ""
        )
        if self.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = self.l10n_ec_identification_type_id.code
        elif self.commercial_partner_id:
            tipoIdentificacionComprador = (
                self.commercial_partner_id.l10n_ec_get_sale_identification_partner()
            )
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = "07"
        SubElement(
            infoNotaCredito, "tipoIdentificacionComprador"
        ).text = tipoIdentificacionComprador
        SubElement(
            infoNotaCredito, "razonSocialComprador"
        ).text = util_model._clean_str(self.commercial_partner_id.name[:300])
        SubElement(
            infoNotaCredito, "identificacionComprador"
        ).text = self.commercial_partner_id.vat
        company = self.env.company
        numero_contribuyente_especial = company.get_contribuyente_data(
            self.invoice_date
        )
        if numero_contribuyente_especial:
            SubElement(
                infoNotaCredito, "contribuyenteEspecial"
            ).text = numero_contribuyente_especial
        SubElement(
            infoNotaCredito, "obligadoContabilidad"
        ).text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id
        )
        if self.l10n_ec_rise:
            SubElement(infoNotaCredito, "rise").text = self.l10n_ec_rise
        # TODO: notas de credito solo se emitiran a facturas o a otros documentos???
        SubElement(infoNotaCredito, "codDocModificado").text = "01"
        SubElement(infoNotaCredito, "numDocModificado").text = (
            self.l10n_ec_legacy_document_number
            or self.l10n_ec_original_invoice_id.l10n_ec_get_document_number()
        )
        SubElement(infoNotaCredito, "fechaEmisionDocSustento").text = (
            self.l10n_ec_legacy_document_date
            or self.l10n_ec_original_invoice_id.l10n_ec_get_document_date()
        ).strftime(util_model.get_formato_date())
        SubElement(
            infoNotaCredito, "totalSinImpuestos"
        ).text = util_model.formato_numero(self.amount_untaxed, currency.decimal_places)
        SubElement(
            infoNotaCredito, "valorModificacion"
        ).text = util_model.formato_numero(self.amount_total, currency.decimal_places)
        SubElement(infoNotaCredito, "moneda").text = (
            self.company_id.currency_id.name or "DOLAR"
        )
        # Definicion de Impuestos
        totalConImpuestos = SubElement(infoNotaCredito, "totalConImpuestos")
        if self.l10n_ec_base_iva_0 != 0:
            self.l10n_ec_get_total_impuestos(
                totalConImpuestos,
                "2",
                "0",
                self.l10n_ec_base_iva_0,
                0.0,
                decimales=currency.decimal_places,
            )
        if self.l10n_ec_base_iva != 0:
            self.l10n_ec_get_total_impuestos(
                totalConImpuestos,
                "2",
                "2",
                self.l10n_ec_base_iva,
                self.l10n_ec_iva,
                decimales=currency.decimal_places,
            )
        # if self.base_no_iva != 0:
        #     self.l10n_ec_get_total_impuestos(totalConImpuestos, '2', '6', self.base_no_iva, 0.0,
        #                              decimales=currency.decimal_places)
        SubElement(infoNotaCredito, "motivo").text = util_model._clean_str(
            self.name and self.name[:300] or "NOTA DE CREDITO"
        )
        # Lineas de Factura
        detalles = SubElement(node, "detalles")
        for line in self.invoice_line_ids.filtered(lambda x: not x.display_type):
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoInterno").text = util_model._clean_str(
                line.product_id
                and line.product_id.default_code
                and line.product_id.default_code[:25]
                or "N/A"
            )
            #             SubElement(detalle,"codigoAdicional").text = util_model._clean_str(line.product_id and line.product_id.default_code and line.product_id.default_code[:25] or 'N/A')
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300]
            )
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(
                line.quantity, digits_precision_qty
            )
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(
                line.price_unit, digits_precision_product
            )
            discount = round(
                ((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2
            )
            # TODO: hacer un redondeo con las utilidades del sistema
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            SubElement(detalle, "descuento").text = util_model.formato_numero(
                discount or 0.0, digits_precision_discount
            )
            SubElement(
                detalle, "precioTotalSinImpuesto"
            ).text = util_model.formato_numero(subtotal, currency.decimal_places)
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "0",
                    line.l10n_ec_base_iva_0,
                    0.0,
                    "impuesto",
                    0,
                    decimales=currency.decimal_places,
                )
            if line.l10n_ec_base_iva != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "2",
                    line.l10n_ec_base_iva,
                    line.l10n_ec_iva,
                    "impuesto",
                    12,
                    decimales=currency.decimal_places,
                )
            # if line.base_no_iva != 0:
            #     self.l10n_ec_get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0,
            #                              decimales=currency.decimal_places)
        self.l10n_ec_add_info_adicional(node)
        return node

    def l10n_ec_get_info_debit_note(self, node):
        util_model = self.env["l10n_ec.utils"]
        company = self.company_id or self.env.company
        currency = company.currency_id
        infoNotaDebito = SubElement(node, "infoNotaDebito")
        fecha_emision = self.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoNotaDebito, "fechaEmision").text = fecha_emision
        address = company.partner_id.street
        SubElement(infoNotaDebito, "dirEstablecimiento").text = util_model._clean_str(
            address and address[:300] or ""
        )
        if self.l10n_ec_identification_type_id:
            tipoIdentificacionComprador = self.l10n_ec_identification_type_id.code
        elif self.commercial_partner_id:
            tipoIdentificacionComprador = (
                self.commercial_partner_id.l10n_ec_get_sale_identification_partner()
            )
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = "07"
        SubElement(
            infoNotaDebito, "tipoIdentificacionComprador"
        ).text = tipoIdentificacionComprador
        SubElement(infoNotaDebito, "razonSocialComprador").text = util_model._clean_str(
            self.commercial_partner_id.name[:300]
        )
        SubElement(
            infoNotaDebito, "identificacionComprador"
        ).text = self.commercial_partner_id.vat
        company = self.env.company
        numero_contribuyente_especial = company.get_contribuyente_data(
            self.invoice_date
        )
        if numero_contribuyente_especial:
            SubElement(
                infoNotaDebito, "contribuyenteEspecial"
            ).text = numero_contribuyente_especial
        SubElement(
            infoNotaDebito, "obligadoContabilidad"
        ).text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id
        )
        if self.l10n_ec_rise:
            SubElement(infoNotaDebito, "rise").text = self.l10n_ec_rise
        # TODO: notas de debito solo se emitiran a facturas o a otros documentos???
        SubElement(infoNotaDebito, "codDocModificado").text = "01"
        SubElement(infoNotaDebito, "numDocModificado").text = (
            self.l10n_ec_legacy_document_number
            or self.debit_origin_id.l10n_ec_get_document_number()
        )
        SubElement(infoNotaDebito, "fechaEmisionDocSustento").text = (
            self.l10n_ec_legacy_document_date
            or self.debit_origin_id.l10n_ec_get_document_date()
        ).strftime(util_model.get_formato_date())
        SubElement(
            infoNotaDebito, "totalSinImpuestos"
        ).text = util_model.formato_numero(self.amount_untaxed)
        # Definicion de Impuestos
        # xq no itero sobre los impuestos???'
        impuestos = SubElement(infoNotaDebito, "impuestos")
        if self.l10n_ec_base_iva_0 != 0:
            self.l10n_ec_get_total_impuestos(
                impuestos,
                "2",
                "0",
                self.l10n_ec_base_iva_0,
                0.0,
                "impuesto",
                0,
                decimales=currency.decimal_places,
            )
        if self.l10n_ec_base_iva != 0:
            # TODO: no se debe asumir que el % del iva es 12, tomar del impuesto directamente
            self.l10n_ec_get_total_impuestos(
                impuestos,
                "2",
                "2",
                self.l10n_ec_base_iva,
                self.l10n_ec_iva,
                "impuesto",
                12,
                decimales=currency.decimal_places,
            )
        # if self.base_no_iva != 0:
        #     self.l10n_ec_get_total_impuestos(impuestos, '2', '6', self.base_no_iva, 0.0, 'impuesto', 0,
        #                              decimales=currency.decimal_places)
        SubElement(infoNotaDebito, "valorTotal").text = util_model.formato_numero(
            self.amount_total, currency.decimal_places
        )
        motivos = SubElement(node, "motivos")
        for line in self.invoice_line_ids.filtered(lambda x: not x.display_type):
            self.l10n_ec_get_motives(
                motivos,
                util_model._clean_str(
                    line.product_id and line.product_id.name[:300] or line.name[:300]
                ),
                line.price_subtotal,
            )
        self.l10n_ec_add_info_adicional(node)
        return node

    def l10n_ec_get_info_liquidation(self, node):
        util_model = self.env["l10n_ec.utils"]
        company = self.company_id or self.env.company
        currency = company.currency_id
        precision_get = self.env["decimal.precision"].precision_get
        digits_precision_product = precision_get("Product Price")
        digits_precision_qty = precision_get("Product Unit of Measure")
        digits_precision_discount = precision_get("Discount")
        infoLiquidacionCompra = SubElement(node, "infoLiquidacionCompra")
        fecha_emision = self.invoice_date.strftime(util_model.get_formato_date())
        SubElement(infoLiquidacionCompra, "fechaEmision").text = fecha_emision
        address = company.partner_id.street
        SubElement(
            infoLiquidacionCompra, "dirEstablecimiento"
        ).text = util_model._clean_str(address and address[:300] or "")
        numero_contribuyente_especial = company.get_contribuyente_data(
            self.invoice_date
        )
        if numero_contribuyente_especial:
            SubElement(
                infoLiquidacionCompra, "contribuyenteEspecial"
            ).text = numero_contribuyente_especial
        SubElement(
            infoLiquidacionCompra, "obligadoContabilidad"
        ).text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id
        )
        if self.commercial_partner_id:
            tipoIdentificacionComprador = (
                self.commercial_partner_id.l10n_ec_get_sale_identification_partner()
            )
        else:
            # si no tengo informacion paso por defecto consumiro final
            # pero debe tener como identificacion 13 digitos 99999999999999
            tipoIdentificacionComprador = "07"
        SubElement(
            infoLiquidacionCompra, "tipoIdentificacionProveedor"
        ).text = tipoIdentificacionComprador
        SubElement(
            infoLiquidacionCompra, "razonSocialProveedor"
        ).text = util_model._clean_str(self.commercial_partner_id.name[:300])
        SubElement(
            infoLiquidacionCompra, "identificacionProveedor"
        ).text = self.commercial_partner_id.vat
        SubElement(
            infoLiquidacionCompra, "direccionProveedor"
        ).text = util_model._clean_str(self.commercial_partner_id.street[:300])
        SubElement(
            infoLiquidacionCompra, "totalSinImpuestos"
        ).text = util_model.formato_numero(
            self.amount_untaxed, decimales=currency.decimal_places
        )
        SubElement(
            infoLiquidacionCompra, "totalDescuento"
        ).text = util_model.formato_numero(
            self.l10n_ec_discount_total, decimales=currency.decimal_places
        )
        if (
            self.l10n_latam_document_type_id
            and self.l10n_latam_document_type_id.code == "41"
        ):
            SubElement(
                infoLiquidacionCompra, "codDocReembolso"
            ).text = self.l10n_latam_document_type_id.code
            SubElement(
                infoLiquidacionCompra, "totalComprobantesReembolso"
            ).text = util_model.formato_numero(
                sum([r.total_invoice for r in self.l10n_ec_refund_ids]),
                decimales=currency.decimal_places,
            )
            SubElement(
                infoLiquidacionCompra, "totalBaseImponibleReembolso"
            ).text = util_model.formato_numero(
                sum([r.total_base_iva for r in self.l10n_ec_refund_ids]),
                decimales=currency.decimal_places,
            )
            SubElement(
                infoLiquidacionCompra, "totalImpuestoReembolso"
            ).text = util_model.formato_numero(
                sum([r.l10n_ec_iva for r in self.l10n_ec_refund_ids])
                + sum([r.total_ice for r in self.l10n_ec_refund_ids]),
                decimales=currency.decimal_places,
            )
        # Definicion de Impuestos
        # xq no itero sobre los impuestos???'
        impuestos = SubElement(infoLiquidacionCompra, "totalConImpuestos")
        if self.l10n_ec_base_iva_0 != 0:
            self.l10n_ec_get_total_impuestos(
                impuestos,
                "2",
                "0",
                self.l10n_ec_base_iva_0,
                0.0,
                "totalImpuesto",
                0,
                False,
                True,
                decimales=currency.decimal_places,
            )
        if self.l10n_ec_base_iva != 0:
            # TODO: no se debe asumir que el % del iva es 12, tomar del impuesto directamente
            self.l10n_ec_get_total_impuestos(
                impuestos,
                "2",
                "2",
                self.l10n_ec_base_iva,
                self.l10n_ec_iva,
                "totalImpuesto",
                12,
                False,
                True,
                decimales=currency.decimal_places,
            )
        # if self.base_no_iva != 0:
        #     self.l10n_ec_get_total_impuestos(impuestos, '2', '6', self.base_no_iva, 0.0, 'totalImpuesto', 0, False, True)
        SubElement(
            infoLiquidacionCompra, "importeTotal"
        ).text = util_model.formato_numero(
            self.amount_total, decimales=currency.decimal_places
        )
        SubElement(
            infoLiquidacionCompra, "moneda"
        ).text = self.company_id.currency_id.name
        payments_data = self.l10n_ec_get_payment_data()
        pagos = SubElement(infoLiquidacionCompra, "pagos")
        for payment_data in payments_data:
            pago = SubElement(pagos, "pago")
            SubElement(pago, "formaPago").text = payment_data["formaPago"]
            SubElement(pago, "total").text = util_model.formato_numero(
                payment_data["total"]
            )
            if payment_data.get("plazo"):
                SubElement(pago, "plazo").text = util_model.formato_numero(
                    payment_data.get("plazo"), 0
                )
                SubElement(pago, "unidadTiempo").text = (
                    payment_data.get("unidadTiempo") or "dias"
                )
        detalles = SubElement(node, "detalles")
        for line in self.invoice_line_ids:
            detalle = SubElement(detalles, "detalle")
            SubElement(detalle, "codigoPrincipal").text = util_model._clean_str(
                line.product_id
                and line.product_id.default_code
                and line.product_id.default_code[:25]
                or "N/A"
            )
            SubElement(detalle, "descripcion").text = util_model._clean_str(
                line.product_id and line.product_id.name[:300] or line.name[:300]
            )
            SubElement(detalle, "unidadMedida").text = (
                line.product_uom_id and line.product_uom_id.display_name or "N/A"
            )
            # Debido a que los precios son en 2 decimales, es necesario hacer razonable el precio unitario
            SubElement(detalle, "cantidad").text = util_model.formato_numero(
                line.quantity, decimales=digits_precision_qty
            )
            SubElement(detalle, "precioUnitario").text = util_model.formato_numero(
                line.price_unit, decimales=digits_precision_product
            )
            discount = round(
                ((line.price_unit * line.quantity) * ((line.discount or 0.0) / 100)), 2
            )
            # TODO: hacer un redondeo con las utilidades del sistema
            subtotal = round(((line.price_unit * line.quantity) - discount), 2)
            SubElement(detalle, "descuento").text = util_model.formato_numero(
                discount or 0.0, decimales=digits_precision_discount
            )
            SubElement(
                detalle, "precioTotalSinImpuesto"
            ).text = util_model.formato_numero(
                subtotal, decimales=currency.decimal_places
            )
            impuestos = SubElement(detalle, "impuestos")
            if line.l10n_ec_base_iva_0 != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "0",
                    line.l10n_ec_base_iva_0,
                    0.0,
                    "impuesto",
                    0,
                    False,
                    decimales=currency.decimal_places,
                )
            if line.l10n_ec_base_iva != 0:
                self.l10n_ec_get_total_impuestos(
                    impuestos,
                    "2",
                    "2",
                    line.l10n_ec_base_iva,
                    line.l10n_ec_iva,
                    "impuesto",
                    12,
                    False,
                    decimales=currency.decimal_places,
                )
            # if line.base_no_iva != 0:
            #     self.l10n_ec_get_total_impuestos(impuestos, '2', '6', line.base_no_iva, 0.0, 'impuesto', 0,
            #     False, decimales=currency.decimal_places)
        # informacion de reembolso solo se debe agregar si el tipo de documento es
        # Comprobante de venta emitido por reembolso(codigo 41)
        if self.l10n_ec_refund_ids:
            reembolsos = SubElement(node, "reembolsos")
            for refund in self.l10n_ec_refund_ids:
                reembolso_detail = SubElement(reembolsos, "reembolsoDetalle")
                tipoIdentificacionComprador = (
                    refund.partner_id.commercial_partner_id.l10n_ec_get_sale_identification_partner()
                )
                SubElement(
                    reembolso_detail, "tipoIdentificacionProveedorReembolso"
                ).text = tipoIdentificacionComprador
                SubElement(
                    reembolso_detail, "identificacionProveedorReembolso"
                ).text = refund.partner_id.commercial_partner_id.vat
                country_code = (
                    refund.partner_id.commercial_partner_id.country_id.phone_code
                    or "593"
                )
                SubElement(
                    reembolso_detail, "codPaisPagoProveedorReembolso"
                ).text = str(country_code)
                SubElement(reembolso_detail, "tipoProveedorReembolso").text = (
                    tipoIdentificacionComprador == "05" and "01" or "02"
                )
                SubElement(reembolso_detail, "codDocReembolso").text = "01"
                agency, printer, sequence = refund.document_number.split("-")
                SubElement(reembolso_detail, "estabDocReembolso").text = agency
                SubElement(reembolso_detail, "ptoEmiDocReembolso").text = printer
                SubElement(reembolso_detail, "secuencialDocReembolso").text = sequence
                fecha_emision = refund.date_invoice.strftime(
                    util_model.get_formato_date()
                )
                SubElement(
                    reembolso_detail, "fechaEmisionDocReembolso"
                ).text = fecha_emision
                SubElement(reembolso_detail, "numeroautorizacionDocReemb").text = (
                    refund.l10n_ec_partner_authorization_id
                    and refund.l10n_ec_partner_authorization_id.number
                    or refund.electronic_authorization
                )
                detalleImpuestos = SubElement(reembolso_detail, "detalleImpuestos")
                tarifa_iva = (
                    refund.total_base_iva
                    and round((refund.total_iva / refund.total_base_iva), 2)
                    or 0.0
                )
                tipo_iva = "2"
                if tarifa_iva == 0.14:
                    tipo_iva = "3"
                if refund.total_base_iva0 != 0:
                    self.l10n_ec_get_total_impuestos(
                        detalleImpuestos,
                        "2",
                        "0",
                        refund.total_base_iva0,
                        0.0,
                        "detalleImpuesto",
                        0,
                        liquidation=True,
                        decimales=currency.decimal_places,
                    )
                if refund.total_base_iva != 0:
                    self.l10n_ec_get_total_impuestos(
                        detalleImpuestos,
                        "2",
                        tipo_iva,
                        refund.total_base_iva,
                        refund.total_iva,
                        "detalleImpuesto",
                        int(tarifa_iva * 100),
                        liquidation=True,
                        refund=True,
                        decimales=currency.decimal_places,
                    )
                if refund.total_base_no_iva != 0:
                    self.l10n_ec_get_total_impuestos(
                        detalleImpuestos,
                        "2",
                        "6",
                        refund.total_base_no_iva,
                        0.0,
                        "detalleImpuesto",
                        0,
                        liquidation=True,
                        decimales=currency.decimal_places,
                    )
        self.l10n_ec_add_info_adicional(node)
        return node

    def l10n_ec_action_sent_mail_electronic(self):
        # reemplazar funcion que es generica en modelo abstracto
        # esta funcion se llama desde el xml electronico para enviar mail al cliente
        MailComposeMessage = self.env["mail.compose.message"]
        self.ensure_one()
        res = self.action_invoice_sent()
        ctx = res["context"]
        msj = MailComposeMessage.with_context(ctx).create({})
        send_mail = True
        try:
            msj.onchange_template_id_wrapper()
            msj.send_mail()
        except Exception:
            send_mail = False
        return send_mail

    def action_invoice_sent(self):
        self.ensure_one()
        res = super(AccountMove, self).action_invoice_sent()
        # si es electronico, cambiar la plantilla de correo a usar
        if self.l10n_ec_xml_data_id:
            template = self.env.ref("l10n_ec_niif.email_template_e_invoice", False)
            if template:
                res["context"]["default_template_id"] = template.id
        return res

    @api.depends(
        "type",
        "l10n_ec_debit_note",
        "l10n_ec_liquidation",
        "l10n_ec_type_emission",
        "company_id.country_id",
    )
    def _compute_readonly_to_electronic_document(self):
        for rec in self:
            l10n_ec_readonly_to_electronic_document = False
            l10n_ec_invoice_type = ""
            l10n_ec_inverse_invoice_type = ""
            if rec.company_id.country_id.code == "EC":
                l10n_ec_invoice_type = rec.l10n_ec_get_invoice_type()
                if l10n_ec_invoice_type:
                    l10n_ec_inverse_invoice_type = modules_mapping.get_document_type(
                        l10n_ec_invoice_type
                    )
                if rec.l10n_ec_type_emission in (
                    "electronic",
                    "auto_printer",
                ) and l10n_ec_invoice_type in (
                    "out_invoice",
                    "out_refund",
                    "liquidation",
                ):
                    l10n_ec_readonly_to_electronic_document = True
            rec.l10n_ec_readonly_to_electronic_document = (
                l10n_ec_readonly_to_electronic_document
            )
            rec.l10n_ec_invoice_type = l10n_ec_invoice_type
            rec.l10n_ec_inverse_invoice_type = l10n_ec_inverse_invoice_type

    l10n_ec_readonly_to_electronic_document = fields.Boolean(
        string="Readonly Electronic Document",
        compute="_compute_readonly_to_electronic_document",
    )
    l10n_ec_invoice_type = fields.Char(
        string="EC Invoice Type", compute="_compute_readonly_to_electronic_document"
    )
    l10n_ec_inverse_invoice_type = fields.Char(
        string="EC Invoice Type(Inverse)",
        compute="_compute_readonly_to_electronic_document",
    )
    l10n_ec_supplier_authorization_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization.supplier",
        string="Supplier Authorization",
        required=False,
    )

    l10n_ec_electronic_authorization = fields.Char(readonly=False)

    @api.onchange("invoice_date")
    def _onchange_invoice_date(self):
        res = super(AccountMove, self)._onchange_invoice_date()
        if self.invoice_date:
            self.l10n_ec_withhold_date = self.invoice_date
        return res

    def _get_name_invoice_report(self, report_xml_id):
        self.ensure_one()
        if self.l10n_latam_use_documents and self.company_id.country_id.code == "EC":
            custom_report = {
                "account.report_invoice_document_with_payments": "l10n_ec_niif.report_invoice_document_with_payments_extension",
                "account.report_invoice_document": "l10n_ec_niif.report_invoice_document_extension",
            }
            return custom_report.get(report_xml_id) or report_xml_id
        return super()._get_name_invoice_report(report_xml_id)


class AccountMoveLine(models.Model):
    _inherit = ["account.move.line", "l10n_ec.common.document.line"]
    _name = "account.move.line"

    l10n_ec_withhold_line_id = fields.Many2one(
        comodel_name="l10n_ec.withhold.line", string="Withhold Line", readonly=True
    )

    def _l10n_ec_get_discount_total(self):
        discount_total = self.price_unit * self.quantity * self.discount * 0.01
        return discount_total

    @api.depends(
        "price_unit",
        "product_id",
        "quantity",
        "discount",
        "tax_ids",
        "move_id.partner_id",
        "move_id.currency_id",
        "move_id.company_id",
        "move_id.invoice_date",
    )
    def _compute_l10n_ec_amounts(self):
        for move_line in self:
            move = move_line.move_id
            move_date = move.date or fields.Date.context_today(move)
            l10n_ec_base_iva_0 = 0.0
            l10n_ec_base_iva = 0.0
            l10n_ec_iva = 0.0
            price_unit_wo_discount = move_line.price_unit * (
                1 - (move_line.discount / 100.0)
            )
            l10n_ec_discount_total = move_line._l10n_ec_get_discount_total()
            taxes_res = move_line.tax_ids._origin.compute_all(
                price_unit_wo_discount,
                quantity=move_line.quantity,
                currency=move.currency_id,
                product=move_line.product_id,
                partner=move.partner_id,
                is_refund=move.type in ("out_refund", "in_refund"),
            )
            # impuestos de iva 0 no agregan reparticion de impuestos,
            # por ahora se consideran base_iva_0, verificar esto
            if taxes_res["taxes"]:
                for tax_data in taxes_res["taxes"]:
                    tax = self.env["account.tax"].browse(tax_data["id"])
                    iva_group = self.env.ref("l10n_ec_niif.tax_group_iva")
                    if tax.tax_group_id.id == iva_group.id:
                        if tax_data["base"] != 0 and tax_data["amount"] == 0:
                            l10n_ec_base_iva_0 = tax_data["base"]
                        else:
                            l10n_ec_base_iva = tax_data["base"]
                            l10n_ec_iva = tax_data["amount"]
            else:
                l10n_ec_base_iva_0 = taxes_res["total_excluded"]
            move_line.l10n_ec_base_iva_0 = l10n_ec_base_iva_0
            move_line.l10n_ec_base_iva = l10n_ec_base_iva
            move_line.l10n_ec_iva = l10n_ec_iva
            move_line.l10n_ec_discount_total = l10n_ec_discount_total
            # FIXME: cuando se crean lineas desde una NC, en el onchange de la factura a rectificar
            # no se tiene aun referencia a la moneda, asi que no hacer conversion de moneda
            if move.currency_id:
                move_line.l10n_ec_base_iva_0_currency = move.currency_id._convert(
                    l10n_ec_base_iva_0,
                    move.company_currency_id,
                    move.company_id,
                    move_date,
                )
                move_line.l10n_ec_base_iva_currency = move.currency_id._convert(
                    l10n_ec_base_iva,
                    move.company_currency_id,
                    move.company_id,
                    move_date,
                )
                move_line.l10n_ec_iva_currency = move.currency_id._convert(
                    l10n_ec_iva, move.company_currency_id, move.company_id, move_date
                )
                move_line.l10n_ec_discount_total_currency = move.currency_id._convert(
                    l10n_ec_discount_total,
                    move.company_currency_id,
                    move.company_id,
                    move_date,
                )
            else:
                move_line.l10n_ec_base_iva_0_currency = l10n_ec_base_iva_0
                move_line.l10n_ec_base_iva_currency = l10n_ec_base_iva
                move_line.l10n_ec_iva_currency = l10n_ec_iva
                move_line.l10n_ec_discount_total_currency = l10n_ec_discount_total
