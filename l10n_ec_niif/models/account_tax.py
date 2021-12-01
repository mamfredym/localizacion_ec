from odoo import api, fields, models


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_ec_xml_fe_code = fields.Char("Tax Code for Electronic Documents", size=5)


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_ec_ats_code = fields.Char(
        "A.T.S. Code",
        size=10,
        help="Tax Code used into A.T.S. report",
    )
    l10n_ec_xml_fe_code = fields.Char(
        "Tax Code for Electronic Documents",
        size=10,
        help="Tax Code used into xml files for electronic documents sent to S.R.I., "
        "If field is empty, description field are used instead",
    )

    @api.model_create_multi
    def create(self, vals):
        recs = super(AccountTax, self).create(vals)
        recs._l10n_ec_action_create_tax_for_withholding()
        return recs

    def _l10n_ec_action_create_tax_for_withholding(self):
        withhold_iva_group = self.env.ref("l10n_ec_niif.tax_group_iva_withhold")
        withhold_rent_group = self.env.ref("l10n_ec_niif.tax_group_renta_withhold")
        percent_model = self.env["l10n_ec.withhold.line.percent"]
        for rec in self:
            if rec.tax_group_id.id in (withhold_iva_group.id, withhold_rent_group.id):
                withhold_type = (
                    rec.tax_group_id.id == withhold_iva_group.id
                    and "iva"
                    or rec.tax_group_id.id == withhold_rent_group.id
                    and "rent"
                )
                percent = abs(rec.amount)
                if withhold_type == "iva":
                    percent = abs(
                        rec.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax").factor_percent
                    )
                current_percent = percent_model.search([("type", "=", withhold_type), ("percent", "=", percent)])
                if not current_percent:
                    percent_model.create(
                        {
                            "name": str(percent),
                            "type": withhold_type,
                            "percent": percent,
                        }
                    )
        return True


class AccountTaxTemplate(models.Model):
    _inherit = "account.tax.template"

    l10n_ec_ats_code = fields.Char(
        "A.T.S. Code",
        size=10,
        help="Tax Code used into A.T.S. report",
    )
    l10n_ec_xml_fe_code = fields.Char(
        "Tax Code for Electronic Documents",
        size=10,
        help="Tax Code used into xml files for electronic documents sent to S.R.I., "
        "If field is empty, description field are used instead",
    )

    def _get_tax_vals(self, company, tax_template_to_tax):
        """This method generates a dictionnary of all the values for the tax that will be created."""
        self.ensure_one()
        val = super(AccountTaxTemplate, self)._get_tax_vals(company, tax_template_to_tax)
        val.update(
            {
                "l10n_ec_ats_code": self.l10n_ec_ats_code,
                "l10n_ec_xml_fe_code": self.l10n_ec_xml_fe_code,
            }
        )
        return val


class AccountTaxRepartitionLine(models.Model):
    _inherit = "account.tax.repartition.line"

    # replace field for change copy attribute
    # at duplicate tax raise error for duplicity
    # on test is need duplicate taxes
    tag_ids = fields.Many2many(copy=False)
