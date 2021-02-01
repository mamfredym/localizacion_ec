import logging
import re

from odoo import api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class WizardCancelElectronicDocuments(models.TransientModel):

    _name = "wizard.cancel.electronic.documents"
    _description = "Wizard to cancel electronic documents"

    move_id = fields.Many2one(comodel_name="account.move", string="Move to cancel", required=False)
    withholding_id = fields.Many2one(comodel_name="l10n_ec.withhold", string="Withholding to cancel", required=False)
    authorization_to_cancel = fields.Char(
        "Authorization Number",
        size=49,
        required=False,
    )

    @api.constrains("authorization_to_cancel")
    def _check_number(self):
        cadena = r"(\d{10}$)|(\d{37}$)|(\d{49}$)"
        for wizard in self:
            if not wizard.authorization_to_cancel:
                continue
            if len(wizard.authorization_to_cancel) not in (10, 37, 49):
                raise ValidationError(_("The authorization number is incorrect, This must be 10, 37 or 49 digits."))
            if not re.match(cadena, wizard.authorization_to_cancel):
                raise ValidationError(_("The electronic authorization must have only numbers"))

    def _cancel_withhold(self):
        action = {"type": "ir.actions.act_window_close"}
        ctx = self.env.context.copy()
        # pasar context para que permita hacer la cancelacion del documento electronico
        ctx["cancel_electronic_document"] = True
        ctx["internal_type"] = "invoice"
        # enviar a cancelar la retencion
        invoice = self.withholding_id.invoice_id
        self.withholding_id.l10n_ec_xml_data_id.write(
            {
                "authorization_to_cancel": self.authorization_to_cancel,
            }
        )
        self.withholding_id.with_context(ctx).action_cancel()
        self.withholding_id.l10n_ec_xml_data_id.action_cancel()
        # quitar la relacion entre las lineas de retencion y la factura para no eliminar la retencion
        self.withholding_id.line_ids.write({"invoice_id": False})
        self.withholding_id.write(
            {
                "invoice_id": False,
            }
        )
        # mostrar la vista de la factura asociada a la retencion
        if invoice:
            # TODO: tratar de cancelar la factura, para enviarla en borrador nuevamente??
            try:
                invoice.with_context(ctx).button_draft()
            except Exception as ex:
                _logger.error(tools.ustr(ex))
                # si hubo un error, talvez la factura esta pagada, el usuario debe hacer el proceso de cancelacion manualmente
            # borrar el numero de retencion
            # para que en caso de validar nuevamente la factura tome otro numero de retencion
            invoice.write({"l10n_ec_withhold_number": False})
            domain = [("id", "in", invoice.ids)]
            action = self.env.ref("account.action_move_in_invoice_type").read()[0]
            action["domain"] = domain
            action["context"] = {
                "create": False,
                "active_model": "account.move",
                "active_id": invoice[0].id,
                "active_ids": invoice.ids,
            }
            if len(invoice) == 1:
                action["views"] = [(False, "form")]
                action["res_id"] = invoice[0].id
        return action

    def _cancel_invoice(self):
        res = {"type": "ir.actions.act_window_close"}
        # si tiene notas de credito debe cancelar las NC antes de cancelar la factura
        if self.move_id.l10n_ec_credit_note_ids.filtered(lambda x: x.state not in ("cancel",)):
            raise UserError(
                _("You cannot cancel the invoice, is used in credit notes, please cancel credit notes first!")
            )
        # si estan pagadas se deben cancelar los pagos antes de cancelar el documento
        if self.move_id.invoice_payment_state != "not_paid":
            raise UserError(_("Invoice is already reconciled, please cancel payments"))
        if self.move_id.l10n_ec_xml_data_id:
            if self.move_id.l10n_ec_xml_data_id.state == "waiting":
                raise UserError(_("Electronic document is waiting authorization, please try in few minutes"))
            self.move_id.l10n_ec_xml_data_id.write(
                {
                    "authorization_to_cancel": self.authorization_to_cancel,
                }
            )
        # pasar context para que permita hacer la cancelacion del documento electronico
        self.move_id.with_context(cancel_electronic_document=True).button_draft()
        self.move_id.with_context(cancel_electronic_document=True).button_cancel()
        return res

    def action_cancel(self):
        res = {"type": "ir.actions.act_window_close"}
        if self.withholding_id:
            if (
                self.withholding_id.invoice_id.invoice_payment_state != "not_paid"
                and self.withholding_id.state == "done"
            ):
                raise UserError(_("You cannot cancel a Withholding Approved was invoice related is Paid"))
            res = self._cancel_withhold()
        elif self.move_id:
            res = self._cancel_invoice()
        return res
