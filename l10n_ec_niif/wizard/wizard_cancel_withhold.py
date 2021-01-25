import re

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


class WizardCancelWithhold(models.TransientModel):

    _name = "wizard.cancel.withhold"

    line_ids = fields.One2many("wizard.cancel.withhold.line", "wizard_id", "Detail")
    date = fields.Date("Date", required=True, default=lambda self: fields.Date.context_today(self))
    company_id = fields.Many2one("res.company", "Company", required=True, default=lambda self: self.env.company)

    def action_cancel_withholding(self):
        retention_model = self.env["l10n_ec.withhold"]
        agency_model = self.env["l10n_ec.agency"]
        printer_model = self.env["l10n_ec.point.of.emission"]
        ret_ids = []
        msj = []
        consumidor_final = self.env.ref("l10n_ec_niif.consumidor_final", False)
        for line in self.line_ids:
            retention_recs = retention_model.search(
                [
                    ("number", "=", line.document_number),
                    ("type", "=", "purchase"),
                    ("company_id", "=", self.company_id.id),
                ]
            )
            document_number = line.document_number.split("-")
            agency_recs = agency_model.search(
                [("number", "=", document_number[0]), ("company_id", "=", self.company_id.id)]
            )
            if not agency_recs:
                raise UserError(_("Cannot find a Agency with SRI number: %s, please check") % (document_number[0]))
            agency_id = agency_recs[0].id
            printer_recs = printer_model.search([("number", "=", document_number[1]), ("agency_id", "=", agency_id)])
            if not printer_recs:
                raise UserError(
                    _("Cannot find a Point emission with number: %s for agency %s, please check")
                    % (document_number[1], document_number[0])
                )
            point_emission = printer_recs[0]
            if not retention_recs:
                doc_find = point_emission.get_authorization_for_number(
                    "withhold_purchase", line.document_number, self.date, self.company_id
                )
                if point_emission.type_emission != "electronic" and not doc_find:
                    msj.append(
                        _("Cannot find a authorization for withholding for number: %s.") % (line.document_number)
                    )
                vals = {
                    "company_id": self.company_id.id,
                    "number": line.document_number,
                    "point_of_emission_id": point_emission.id,
                    "document_type": point_emission.type_emission,
                    "authorization_line_id": doc_find.id,
                    "partner_id": line.partner_id.id if line.partner_id else consumidor_final.id,
                    "state": "cancelled",
                    "issue_date": self.date,
                    "type": "purchase",
                    "note": _("Withholding cancel"),
                }
                new_retention = retention_model.create(vals)
                ret_ids.append(new_retention.id)
            else:
                for ret in retention_recs:
                    if ret.invoice_id:
                        if ret.invoice_id.state not in (
                            "draft",
                            "cancel",
                        ):
                            msj.append(
                                "Already exists  a withholding with number: %s associated to invoice: %s for supplier: %s."
                                % (
                                    ret.l10n_ec_get_document_number(),
                                    ret.invoice_id.l10n_ec_get_document_number(),
                                    ret.invoice_id.partner_id.display_name,
                                )
                            )
                    else:
                        msj.append(
                            _("Already exists  a withholding with number %s.") % (ret.l10n_ec_get_document_number())
                        )
        if msj:
            raise UserError("\n".join(msj))
        action = {"type": "ir.actions.act_window_close"}
        if ret_ids:
            domain = [("id", "in", ret_ids)]
            action = self.env.ref("l10n_ec_niif.l10n_ec_withhold_purchase_act_window").read()[0]
            form_view = self.env.ref("l10n_ec_niif.l10n_ec_withhold_form_view", False)
            action["domain"] = domain
            action["context"] = {
                "create": False,
                "active_model": retention_model._name,
                "active_id": ret_ids[0],
                "active_ids": ret_ids,
            }
            if len(ret_ids) == 1:
                action["views"] = [(form_view and form_view.id or False, "form")]
                action["res_id"] = ret_ids[0]
        return action


class WizardCancelWithholdLine(models.TransientModel):

    _name = "wizard.cancel.withhold.line"
    _description = "Wizard detail for create withholding cancelled"

    wizard_id = fields.Many2one("wizard.cancel.withhold", "Wizard", ondelete="cascade")
    document_number = fields.Char("Document Number", size=17, required=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
    )

    @api.onchange("document_number")
    def _onchange_document_number(self):
        UtilModel = self.env["l10n_ec.utils"]
        auth_supplier_model = self.env["l10n_ec.sri.authorization.supplier"]
        padding = 9
        warning = {}
        if self.document_number:
            try:
                (
                    agency,
                    printer_point,
                    sequence_number,
                ) = UtilModel.split_document_number(self.document_number, True)
                sequence_number = int(sequence_number)
                sequence_number = auth_supplier_model.fill_padding(sequence_number, padding)
                document_number = f"{agency}-{printer_point}-{sequence_number}"
                self.document_number = document_number
            except Exception as ex:
                warning = {
                    "title": _("Information for User"),
                    "message": _(
                        "The document number is not valid, must be as 00X-00X-000XXXXXX, Where X is a number\n %s"
                    )
                    % tools.ustr(ex),
                }
        return {"warning": warning}

    @api.constrains("document_number")
    def _check_document_number(self):
        cadena = re.compile(r"(\d{3})+\-(\d{3})+\-(\d{9})")
        for line in self:
            if line.document_number and not re.match(cadena, line.document_number):
                raise ValidationError(
                    _("The document number: %s is not valid, must be as 00X-00X-000XXXXXX, Where X is a number")
                    % line.document_number
                )
