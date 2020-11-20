from odoo import models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def generate_email(self, res_ids, fields=None):
        self.ensure_one()
        res = super(MailTemplate, self).generate_email(res_ids, fields=fields)
        if self.model not in (
            "account.move",
            "l10n_ec.delivery.note",
            "l10n_ec.withhold",
        ):
            return res
        multi_mode = True
        if isinstance(res_ids, int):
            res_ids = [res_ids]
            multi_mode = False
        for document in self.env[self.model].browse(res_ids).filtered("l10n_ec_xml_data_id"):
            attachment = document.l10n_ec_action_create_attachments_electronic()
            if attachment:
                if multi_mode:
                    res[document.id].setdefault("attachment_ids", []).append(attachment.id)
                else:
                    res.setdefault("attachment_ids", []).append(attachment.id)
        return res
