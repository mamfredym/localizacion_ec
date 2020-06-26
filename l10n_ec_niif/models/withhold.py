import re
from xml.etree.ElementTree import SubElement

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_STATES = {"draft": [("readonly", False)]}


class L10nEcWithhold(models.Model):

    _name = "l10n_ec.withhold"
    _inherit = [
        "portal.mixin",
        "mail.thread",
        "mail.activity.mixin",
        "l10n_ec.common.document.electronic",
    ]
    _description = "Ecuadorian Withhold"
    _rec_name = "number"
    _mail_post_access = "read"
    _order = "issue_date DESC, number DESC"

    company_id = fields.Many2one(
        "res.company",
        "Company",
        required=True,
        ondelete="restrict",
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Currency", related="company_id.currency_id", store=True,
    )
    number = fields.Char(
        string="Number", required=True, readonly=True, states=_STATES, tracking=True
    )
    no_number = fields.Boolean("Withholding  without Number?")
    state = fields.Selection(
        string="State",
        selection=[("draft", "Draft"), ("done", "Done"), ("cancelled", "Cancelled"),],
        required=True,
        readonly=True,
        default="draft",
        tracking=True,
    )
    issue_date = fields.Date(
        string="Issue date", readonly=True, states=_STATES, required=True, tracking=True
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        readonly=True,
        ondelete="restrict",
        states=_STATES,
        required=True,
        tracking=True,
    )
    commercial_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Commercial partner",
        readonly=True,
        ondelete="restrict",
        related="partner_id.commercial_partner_id",
        store=True,
        tracking=True,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Related Document",
        readonly=True,
        states=_STATES,
        required=False,
        tracking=True,
    )
    partner_authorization_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization.supplier",
        string="Partner authorization",
        readonly=True,
        states=_STATES,
        required=False,
        tracking=True,
    )
    type = fields.Selection(
        string="Type",
        selection=[
            ("sale", "On Sales"),
            ("purchase", "On Purchases"),
            ("credit_card", "On Credit Card Liquidation"),
        ],
        required=True,
        readonly=True,
        deafult=lambda self: self.env.context.get("withhold_type", "sale"),
    )
    document_type = fields.Selection(
        string="Document type",
        selection=[
            ("electronic", "Electronic"),
            ("pre_printed", "Pre Printed"),
            ("auto_printer", "Auto Printer"),
        ],
        required=True,
        readonly=True,
        states=_STATES,
        default="electronic",
        tracking=True,
    )
    electronic_authorization = fields.Char(
        string="Electronic authorization",
        size=49,
        readonly=True,
        states=_STATES,
        required=False,
        tracking=True,
    )
    point_of_emission_id = fields.Many2one(
        comodel_name="l10n_ec.point.of.emission",
        string="Point of Emission",
        ondelete="restrict",
        readonly=True,
        states=_STATES,
    )
    agency_id = fields.Many2one(
        comodel_name="l10n_ec.agency",
        string="Agency",
        related="point_of_emission_id.agency_id",
        ondelete="restrict",
        store=True,
        readonly=True,
    )
    authorization_line_id = fields.Many2one(
        comodel_name="l10n_ec.sri.authorization.line",
        string="Own Ecuadorian Authorization Line",
        ondelete="restrict",
        readonly=True,
        states=_STATES,
    )
    concept = fields.Char(
        string="Concept", readonly=True, states=_STATES, required=False, tracking=True
    )
    note = fields.Char(string="Note", required=False)
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Account Move",
        ondelete="restrict",
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name="l10n_ec.withhold.line",
        inverse_name="withhold_id",
        string="Lines",
        readonly=True,
        states=_STATES,
        required=True,
    )

    @api.depends(
        "line_ids.type", "line_ids.tax_amount",
    )
    def _compute_tax_amount(self):
        for rec in self:
            rec.tax_iva = sum(
                i.tax_amount_currency
                for i in rec.line_ids.filtered(lambda x: x.type == "iva")
            )
            rec.tax_rent = sum(
                r.tax_amount_currency
                for r in rec.line_ids.filtered(lambda x: x.type == "rent")
            )

    tax_iva = fields.Monetary(
        string="Withhold IVA", compute="_compute_tax_amount", store=True, readonly=True
    )
    tax_rent = fields.Monetary(
        string="Withhold Rent", compute="_compute_tax_amount", store=True, readonly=True
    )
    l10n_ec_related_document = fields.Boolean(
        string="Have related document?", compute="_compute_is_related_document"
    )
    l10n_ec_is_create_from_invoice = fields.Boolean(string="Is created from invoice?")
    move_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="l10n_ec_withhold_id",
        string="Accounting entries",
    )
    move_count = fields.Integer(
        string="Move Count", compute="_compute_l10n_ec_withhold_ids", store=False
    )

    @api.depends("invoice_id")
    def _compute_is_related_document(self):
        for rec in self:
            rec.l10n_ec_related_document = False
            if rec.invoice_id:
                rec.l10n_ec_related_document = True

    def _format_withhold_document_number(self, document_number):
        self.ensure_one()
        if not document_number:
            return False
        if not re.match(r"\d{3}-\d{3}-\d{9}$", document_number):
            raise UserError(
                _("Ecuadorian Document %s must be like 001-001-123456789")
                % (self.display_name)
            )
        return document_number

    @api.constrains("invoice_id")
    def _check_no_retention_same_invoice(self):
        for rec in self:
            l10n_ec_withhold_line_ids = rec.search(
                [("invoice_id", "=", rec.invoice_id.id), ("id", "!=", rec.id)]
            )
            if l10n_ec_withhold_line_ids:
                raise UserError(_("Factura ya es registrada"))
        return True

    @api.onchange("number")
    def _onchange_number_sale_withhold(self):
        for rec in self:
            if rec.number:
                format_document_number = rec._format_withhold_document_number(
                    rec.number
                )
                if rec.number != format_document_number:
                    rec.number = format_document_number

    def action_done(self):
        model_move = self.env["account.move"]
        model_aml = self.env["account.move.line"]

        def _create_move_line(
            move_id,
            credit,
            debit,
            account_id,
            tax_code_id=None,
            tax_amount=0.0,
            name="/",
            partner_id=None,
        ):
            vals_move_line = {
                "move_id": move_id,
                "account_id": account_id,
                "tag_ids": tax_code_id,
                "tax_base_amount": tax_amount,
                "debit": debit,
                "credit": credit,
                "name": name,
                "partner_id": partner_id,
            }
            return model_aml.with_context(check_move_validity=False).create(
                vals_move_line
            )

        if self.type == "sale":
            destination_account_id = self.partner_id.property_account_receivable_id
            if not self.line_ids:
                raise UserError(_("You must have at least one line to continue"))
            vals_move = {
                "ref": _("RET CLI: %s") % self.number,
                "date": self.issue_date,
                "company_id": self.company_id.id,
                "state": "draft",
                "journal_id": self.company_id.l10n_ec_withhold_journal_id.id,
                "type": "entry",
                "l10n_ec_withhold_id": self.id,
            }
            move_rec = model_move.create(vals_move)
            total_detained_iva = 0.0
            total_detained_rent = 0.0
            invoices = self.invoice_id
            for line in self.line_ids:
                if not invoices:
                    invoices |= line.invoice_id
                if line.type == "iva":
                    total_detained_iva += line.tax_amount
                elif line.type == "rent":
                    total_detained_rent += line.tax_amount
            if total_detained_iva > 0:
                _create_move_line(
                    move_rec.id,
                    0.0,
                    total_detained_iva,
                    self.company_id.l10n_ec_withhold_sale_iva_account_id.id,
                    self.company_id.l10n_ec_withhold_sale_iva_tag_id.ids,
                    total_detained_iva,
                    name=_("IVA RETENIDO RET. %s") % self.number,
                )
            if total_detained_rent > 0:
                _create_move_line(
                    move_rec.id,
                    0.0,
                    total_detained_rent,
                    self.company_id.l10n_ec_withhold_sale_rent_account_id.id,
                    name=_("I.R. RETENIDO RET. %s") % self.number,
                )
            move_line = model_aml.browse()
            if invoices:
                move_line = invoices.line_ids.filtered(
                    lambda l: not l.reconciled
                    and l.account_id == destination_account_id
                )
            if not move_line:
                raise UserError(_("There is no outstanding balance on this invoice"))
            lines_to_reconcile = model_aml.browse()
            lines_to_reconcile += move_line
            lines_to_reconcile += _create_move_line(
                move_rec.id,
                total_detained_iva + total_detained_rent,
                0.0,
                destination_account_id.id,
                name=_("CRUCE RET. %s con %s")
                % (self.number, self.invoice_id.display_name),
                partner_id=self.partner_id.id,
            )
            lines_to_reconcile.reconcile()
        self.write(
            {"state": "done",}
        )

    def action_cancel(self):
        for withholding in self:
            # TODO: realizar proceso de anulacion de una retencion en ventas
            if withholding.type == "purchase":
                withholding.write({"state": "cancelled"})
        return True

    @api.depends("move_ids",)
    def _compute_l10n_ec_withhold_ids(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    def action_show_move(self):
        self.ensure_one()
        type = self.mapped("type")[0]
        action = self.env.ref("account.action_move_journal_line").read()[0]

        moves = self.mapped("move_ids")
        if len(moves) > 1:
            action["domain"] = [("id", "in", moves.ids)]
        elif moves:
            action["views"] = [(self.env.ref("account.view_move_form").id, "form")]
            action["res_id"] = moves.id
        action["context"] = dict(
            self._context,
            default_partner_id=self.partner_id.id,
            default_l10n_ec_withhold_id=self.id,
        )
        return action

    def unlink(self):
        for rec in self:
            if rec.state != "draft" and not self.env.context.get("cancel_from_invoice"):
                raise UserError(_("You cannot delete an approved hold"))
        return super(L10nEcWithhold, self).unlink()

    # bloque de codigo para generar documento electronico

    def l10n_ec_get_document_code_sri(self):
        return "07"

    def l10n_ec_get_document_number(self):
        # esta funcion debe devolver el numero de documento
        return self.number

    def l10n_ec_get_document_date(self):
        # esta funcion debe devolver la fecha de emision del documento
        return self.issue_date

    def l10n_ec_get_document_version_xml(self):
        # esta funcion debe devolver la version del xml que se debe usar
        company = self.company_id or self.env.company
        return company.l10n_ec_withholding_version_xml_id

    def l10n_ec_get_document_filename_xml(self):
        # esta funcion debe devolver el nombre del archivo xml sin la extension
        # algo como: id, prefijo, secuencial
        return f"{self.id}_RET_{self.l10n_ec_get_document_number()}"

    def l10n_ec_action_generate_xml_data(self, node_root):
        util_model = self.env["l10n_ec.utils"]
        company = self.company_id or self.env.company
        infoCompRetencion = SubElement(node_root, "infoCompRetencion")
        SubElement(infoCompRetencion, "fechaEmision").text = self.issue_date.strftime(
            util_model.get_formato_date()
        )
        address = company.partner_id.street
        SubElement(
            infoCompRetencion, "dirEstablecimiento"
        ).text = util_model._clean_str(address[:300])
        numero_contribuyente_especial = company.get_contribuyente_data(self.issue_date)
        SubElement(
            infoCompRetencion, "contribuyenteEspecial"
        ).text = numero_contribuyente_especial
        SubElement(
            infoCompRetencion, "obligadoContabilidad"
        ).text = util_model.get_obligado_contabilidad(
            company.partner_id.property_account_position_id
        )
        SubElement(
            infoCompRetencion, "tipoIdentificacionSujetoRetenido"
        ).text = self.get_identification_type_partner(
            self.partner_id.commercial_partner_id
        )
        SubElement(
            infoCompRetencion, "razonSocialSujetoRetenido"
        ).text = util_model._clean_str(self.partner_id.commercial_partner_id.name)
        SubElement(
            infoCompRetencion, "identificacionSujetoRetenido"
        ).text = util_model._clean_str(self.partner_id.commercial_partner_id.vat)
        SubElement(infoCompRetencion, "periodoFiscal").text = self.issue_date.strftime(
            "%m/%Y"
        )
        impuestos = SubElement(node_root, "impuestos")
        for line in self.line_ids:
            impuesto = SubElement(impuestos, "impuesto")
            SubElement(impuesto, "codigo").text = line.get_retention_code()
            SubElement(impuesto, "codigoRetencion").text = line.get_retention_tax_code()
            SubElement(impuesto, "baseImponible").text = util_model.formato_numero(
                line.base_amount
            )
            SubElement(impuesto, "porcentajeRetener").text = util_model.formato_numero(
                line.percentage, 2
            )
            SubElement(impuesto, "valorRetenido").text = util_model.formato_numero(
                line.tax_amount
            )
            SubElement(impuesto, "codDocSustento").text = (
                self.invoice_id.l10n_ec_get_document_code_sri() or "01"
            )
            numDocSustento = self.invoice_id.l10n_ec_get_document_number()
            dateDocSustento = self.invoice_id.l10n_ec_get_document_date()
            SubElement(impuesto, "numDocSustento").text = numDocSustento.replace(
                "-", ""
            )  # pasar numero sin guiones
            SubElement(
                impuesto, "fechaEmisionDocSustento"
            ).text = dateDocSustento.strftime(util_model.get_formato_date())
        self.l10n_ec_add_info_adicional(node_root)
        return node_root


class L10nEcWithholdLinePercent(models.Model):

    _name = "l10n_ec.withhold.line.percent"
    _order = "percent ASC"

    name = fields.Char(string="Percent", required=False)
    type = fields.Selection(
        string="Type", selection=[("iva", "IVA"), ("rent", "Rent"),], required=False,
    )
    percent = fields.Float(string="Percent", required=False)

    def _get_percent(self, percent, type):
        rec = self.search([("type", "=", type), ("percent", "=", percent),])
        if not rec:
            rec = self.create({"name": str(percent), "type": type, "percent": percent,})
        return rec

    _sql_constraints = [
        (
            "type_percent_unique",
            "unique(type, percent)",
            "Percent Withhold must be unique by type",
        )
    ]


class AccountTax(models.Model):

    _inherit = "account.tax"

    def create(self, vals):
        recs = super(AccountTax, self).create(vals)
        withhold_iva_group = self.env.ref("l10n_ec_niif.tax_group_iva_withhold")
        withhold_rent_group = self.env.ref("l10n_ec_niif.tax_group_renta_withhold")
        percent_model = self.env["l10n_ec.withhold.line.percent"]
        for rec in recs:
            if rec.tax_group_id.id in (withhold_iva_group.id, withhold_rent_group.id):
                type = (
                    rec.tax_group_id.id == withhold_iva_group.id
                    and "iva"
                    or rec.tax_group_id.id == withhold_rent_group.id
                    and "rent"
                )
                percent = abs(rec.amount)
                if type == "iva":
                    percent = abs(
                        rec.invoice_repartition_line_ids.filtered(
                            lambda x: x.repartition_type == "tax"
                        ).factor_percent
                    )
                current_percent = percent_model.search(
                    [("type", "=", type), ("percent", "=", percent)]
                )
                if not current_percent:
                    percent_model.create(
                        {"name": str(percent), "type": type, "percent": percent,}
                    )
        return recs


class L10nEcWithholdLine(models.Model):

    _name = "l10n_ec.withhold.line"
    _description = "Ecuadorian Withhold"

    withhold_id = fields.Many2one(
        comodel_name="l10n_ec.withhold",
        string="Withhold",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        related="withhold_id.company_id",
        store=True,
    )
    issue_date = fields.Date(
        string="Issue date", related="withhold_id.issue_date", store=True,
    )
    invoice_id = fields.Many2one(
        comodel_name="account.move", string="Related Document", required=False
    )
    tax_id = fields.Many2one(comodel_name="account.tax", string="Tax", required=False)
    base_tag_id = fields.Many2one(
        comodel_name="account.account.tag", string="Base Tax Tag", readonly=True
    )
    tax_tag_id = fields.Many2one(
        comodel_name="account.account.tag", string="Tax Tax Tag", readonly=True
    )
    type = fields.Selection(
        string="Type", selection=[("iva", "IVA"), ("rent", "Rent"),], required=True,
    )
    partner_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Partner Currency",
        related="invoice_id.currency_id",
        store=True,
    )
    base_amount = fields.Monetary(
        string="Base Amount Currency",
        currency_field="partner_currency_id",
        required=True,
    )
    tax_amount = fields.Monetary(
        string="Withhold Amount Currency",
        currency_field="partner_currency_id",
        required=True,
    )
    percent_id = fields.Many2one(
        comodel_name="l10n_ec.withhold.line.percent", string="Percent", required=False
    )
    percentage = fields.Float(
        string="Percent", related="percent_id.percent", store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="withhold_id.currency_id",
        store=True,
    )
    base_amount_currency = fields.Monetary(string="Base Amount", required=True)
    tax_amount_currency = fields.Monetary(string="Withhold Amount", required=True)

    @api.onchange(
        "invoice_id", "type",
    )
    def _onchange_invoice(self):
        if self.invoice_id:
            base_amount = 0
            if self.type == "iva":
                base_amount = self.invoice_id.l10n_ec_iva
            elif self.type == "rent":
                base_amount = self.invoice_id.amount_untaxed
            self.update({"base_amount": base_amount})

    @api.onchange(
        "percent_id", "base_amount",
    )
    def _onchange_amount(self):
        if self.percent_id:
            self.base_amount_currency = self.partner_currency_id.compute(
                self.base_amount, self.currency_id
            )
            self.tax_amount = (self.percent_id.percent / 100.0) * self.base_amount
            self.tax_amount_currency = self.partner_currency_id.compute(
                self.tax_amount, self.currency_id
            )

    def get_retention_code(self):
        self.ensure_one()
        retention_code = "6"
        if self.type == "iva":
            retention_code = "2"
        elif self.type == "rent":
            retention_code = "1"
        return retention_code

    def get_retention_tax_code(self):
        if self.type == "iva":
            if self.percentage == 10.0:
                return "9"
            elif self.percentage == 20.0:
                return "10"
            elif self.percentage == 30.0:
                return "1"
            elif self.percentage == 50.0:
                return "11"
            elif self.percentage == 70.0:
                return "2"
            elif self.percentage == 100.0:
                return "3"
        elif self.type == "rent":
            return self.tax_id.description
