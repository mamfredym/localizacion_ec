import re
from xml.etree.ElementTree import SubElement

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

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
        string="Number",
        required=True,
        readonly=True,
        states=_STATES,
        tracking=True,
        size=17,
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
    l10n_ec_legacy_document = fields.Boolean(
        string="Is External Doc. Modified?",
        readonly=True,
        states=_STATES,
        help="With this option activated, the system will not require an invoice to issue the Debut or Credit Note",
    )
    l10n_ec_legacy_document_date = fields.Date(
        string="External Document Date", readonly=True, states=_STATES,
    )
    l10n_ec_legacy_document_number = fields.Char(
        string="External Document Number", readonly=True, states=_STATES,
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

    @api.constrains("l10n_ec_legacy_document_number")
    @api.onchange("l10n_ec_legacy_document_number")
    def _check_l10n_ec_legacy_document_number(self):
        for withhold in self:
            if withhold.l10n_ec_legacy_document_number:
                withhold._format_withhold_document_number(
                    withhold.l10n_ec_legacy_document_number
                )

    def _compute_access_url(self):
        super(L10nEcWithhold, self)._compute_access_url()
        for withhold in self:
            withhold.access_url = "/my/retencion/%s" % (withhold.id)

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
                raise UserError(_("Invoice is already registered"))
        return True

    @api.onchange("number")
    @api.constrains("number")
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
        authorization_supplier_model = self.env["l10n_ec.sri.authorization.supplier"]

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

        for rec in self:
            if rec.type == "sale":
                authorization_supplier_model.validate_unique_document_partner(
                    "withhold_sale", rec.number, rec.partner_id.id, rec.id,
                )
                if rec.document_type in ("pre_printed", "auto_printer"):
                    if rec.partner_authorization_id:
                        authorization_supplier_model.check_number_document(
                            "withhold_sale",
                            rec.number,
                            rec.partner_authorization_id,
                            rec.issue_date,
                            rec.id,
                            False,
                        )
                    else:
                        raise UserError(
                            _("You must enter the authorization of the third party")
                        )
                destination_account_id = rec.partner_id.property_account_receivable_id
                if not rec.line_ids:
                    raise UserError(_("You must have at least one line to continue"))
                if not rec.company_id.l10n_ec_withhold_journal_id:
                    raise UserError(
                        _("You must configure Withhold Journal on Company to continue")
                    )
                if not rec.company_id.l10n_ec_withhold_sale_iva_account_id:
                    raise UserError(
                        _(
                            "You must configure Withhold Sale Vat Account on Company to continue"
                        )
                    )
                if not rec.company_id.l10n_ec_withhold_sale_rent_account_id:
                    raise UserError(
                        _(
                            "You must configure Withhold Sale Rent Account on Company to continue"
                        )
                    )
                vals_move = {
                    "ref": _("RET CLI: %s") % rec.number,
                    "date": rec.issue_date,
                    "company_id": rec.company_id.id,
                    "state": "draft",
                    "journal_id": rec.company_id.l10n_ec_withhold_journal_id.id,
                    "type": "entry",
                    "l10n_ec_withhold_id": rec.id,
                    "currency_id": rec.line_ids.mapped("currency_id").id
                    or self.env.company.currency_id.id,
                }
                move_rec = model_move.create(vals_move)
                rec.move_id = move_rec.id
                invoice_group_to_reconcile = {}
                for line in rec.line_ids:
                    invoice_group_to_reconcile.setdefault(
                        line.invoice_id.id, model_aml.browse()
                    )
                    for aml in line.invoice_id.line_ids.filtered(
                        lambda line: not line.reconciled
                        and line.account_id == destination_account_id
                        and line.partner_id.id == line.move_id.partner_id.id
                    ):
                        invoice_group_to_reconcile[line.invoice_id.id] |= aml
                    if line.tax_amount > 0:
                        account_id = False
                        tax_code = False
                        name = False
                        if line.type == "iva":
                            account_id = (
                                rec.company_id.l10n_ec_withhold_sale_iva_account_id.id
                            )
                            tax_code = (
                                rec.company_id.l10n_ec_withhold_sale_iva_tag_id.ids
                            )
                            name = _("Withhold Vat. %s") % line.invoice_id.display_name
                        elif line.type == "rent":
                            account_id = (
                                rec.company_id.l10n_ec_withhold_sale_rent_account_id.id
                            )
                            tax_code = []
                            name = (
                                _("Withhold Rent Tax. %s")
                                % line.invoice_id.display_name
                            )
                        _create_move_line(
                            move_id=move_rec.id,
                            credit=0.0,
                            debit=line.tax_amount,
                            account_id=account_id,
                            tax_code_id=tax_code,
                            tax_amount=line.tax_amount,
                            name=name,
                        )
                        invoice_group_to_reconcile[
                            line.invoice_id.id
                        ] |= _create_move_line(
                            move_id=move_rec.id,
                            credit=line.tax_amount,
                            debit=0.0,
                            account_id=destination_account_id.id,
                            tax_code_id=[],
                            tax_amount=line.tax_amount,
                            name=name,
                        )
                for invoice_id in invoice_group_to_reconcile.keys():
                    if len(invoice_group_to_reconcile[invoice_id]) > 1:
                        invoice_group_to_reconcile[invoice_id].reconcile()
                move_rec.action_post()
        self.write(
            {"state": "done",}
        )

    def action_back_to_draft(self):
        return self.write({"state": "draft",})

    def action_cancel(self):
        for rec in self:
            if rec.type == "sale":
                if rec.move_id:
                    rec.move_id.button_cancel()
                    rec.move_id.line_ids.remove_move_reconcile()
                    current_move = rec.move_id
                    rec.move_id = False
                    current_move.unlink()
        return self.write({"state": "cancelled"})

    @api.depends("move_ids",)
    def _compute_l10n_ec_withhold_ids(self):
        for rec in self:
            rec.move_count = len(rec.move_ids)

    def action_show_move(self):
        self.ensure_one()
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

    def _l10n_ec_add_followers_to_electronic_documents(self):
        partners = self.env["res.partner"].browse()
        if (
            self.commercial_partner_id.l10n_ec_email_withhold_purchase
            and self.commercial_partner_id not in self.message_partner_ids
        ):
            partners |= self.commercial_partner_id
        for contact in self.commercial_partner_id.child_ids:
            if (
                contact.l10n_ec_email_withhold_purchase
                and contact not in self.message_partner_ids
            ):
                partners |= contact
        if partners:
            self.message_subscribe(partners.ids)
        return True

    def l10n_ec_get_document_code_sri(self):
        return "07"

    def l10n_ec_get_document_number(self):
        # esta funcion debe devolver el numero de documento
        return self.number

    def l10n_ec_get_document_date(self):
        # esta funcion debe devolver la fecha de emision del documento
        return self.issue_date

    def l10n_ec_get_document_string(self):
        return "Retencion"

    def l10n_ec_get_document_version_xml(self):
        # esta funcion debe devolver la version del xml que se debe usar
        company = self.company_id or self.env.company
        return company.l10n_ec_withholding_version_xml_id

    def l10n_ec_get_document_filename_xml(self):
        # esta funcion debe devolver el nombre del archivo xml sin la extension
        # algo como: id, prefijo, secuencial
        return f"{self.id}_RET_{self.l10n_ec_get_document_number()}"

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"RET-{self.l10n_ec_get_document_number()}"

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
        if numero_contribuyente_especial:
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
        ).text = (
            self.partner_id.commercial_partner_id.l10n_ec_get_sale_identification_partner()
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

    def action_sent_mail_electronic(self):
        self.ensure_one()
        template = self.env.ref("l10n_ec_niif.email_template_e_retention", False)
        ctx = {
            "default_model": self._name,
            "default_res_id": self.id,
            "default_use_template": bool(template),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "custom_layout": "mail.mail_notification_light",
            "force_email": True,
            "model_description": self.l10n_ec_get_document_string(),
        }
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(False, "form")],
            "view_id": False,
            "target": "new",
            "context": ctx,
        }

    def l10n_ec_action_sent_mail_electronic(self):
        MailComposeMessage = self.env["mail.compose.message"]
        self.ensure_one()
        template = self.env.ref("l10n_ec_niif.email_template_e_retention", False)
        ctx = {
            "default_model": self._name,
            "default_res_id": self.id,
            "default_use_template": bool(template),
            "default_template_id": template.id,
            "default_composition_mode": "comment",
            "custom_layout": "mail.mail_notification_light",
            "force_email": True,
            "model_description": self.l10n_ec_get_document_string(),
        }
        msj = MailComposeMessage.with_context(ctx).create({})
        send_mail = True
        try:
            msj.onchange_template_id_wrapper()
            msj.send_mail()
        except Exception:
            send_mail = False
        return send_mail

    def l10n_ec_get_share_url(self, redirect=False, signup_partner=False, pid=None):
        # funcion para usarla desde los correos electronicos
        # el metodo original al ser privado no permite llamarlo desde la plantilla de correo
        return self._get_share_url(
            redirect=redirect, signup_partner=signup_partner, pid=pid
        )

    @api.constrains(
        "number", "type", "company_id",
    )
    def _check_number_duplicity(self):
        for rec in self:
            if rec.type == "purchase":
                other_records = self.search(
                    [
                        ("type", "=", "purchase"),
                        ("number", "=", rec.number),
                        ("company_id", "=", rec.company_id.id),
                    ]
                )
                if len(other_records) > 1:
                    raise ValidationError(
                        _(
                            "There is already a withhold on sales with number %s please verify"
                        )
                        % (rec.number)
                    )

    @api.constrains("electronic_authorization")
    def _check_duplicity_electronic_authorization(self):
        for rec in self:
            if rec.electronic_authorization:
                other_docs = self.search(
                    [("electronic_authorization", "=", rec.electronic_authorization,),]
                )
                if len(other_docs) > 1:
                    raise ValidationError(
                        _(
                            "There is already a document with electronic authorization %s please verify"
                        )
                        % (rec.electronic_authorization)
                    )


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
        comodel_name="account.move",
        string="Related Document",
        required=False,
        default=lambda self: self.env.context.get("default_invoice_id", False),
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
        if not self.invoice_id:
            if self.env.context.get("active_model", False) == "account.move":
                if self.env.context.get("active_id", False):
                    self.invoice_id = self.env.context.get("active_id", False)
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
        if self.tax_id.tax_group_id.l10n_ec_xml_fe_code:
            retention_code = self.tax_id.tax_group_id.l10n_ec_xml_fe_code
        return retention_code

    def get_retention_tax_code(self):
        if self.type == "iva":
            return self.tax_id.l10n_ec_xml_fe_code
        elif self.type == "rent":
            return self.tax_id.description
