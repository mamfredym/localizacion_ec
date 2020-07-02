from odoo import api, fields, models


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_ec_xml_fe_code = fields.Char(u"Codigo en Facturacion electronica", size=5)


class AccountTax(models.Model):
    _inherit = "account.tax"

    l10n_ec_ats_code = fields.Char(
        "Código en A.T.S.",
        size=10,
        help="Indica el codigo usado en el Anexo Transaccional Simplificado del SRI",
    )
    l10n_ec_xml_fe_code = fields.Char(
        "Código en Facturacion electronica",
        size=10,
        help="Indica el codigo usado en el xml de facturacion electronica que se envia al SRI, "
        "en caso de no estar configrado se tomara el codigo de impuesto normal",
    )


class AccountTaxTemplate(models.Model):
    _inherit = "account.tax.template"

    l10n_ec_ats_code = fields.Char(
        "Código en A.T.S.",
        size=10,
        help="Indica el codigo usado en el Anexo Transaccional Simplificado del SRI",
    )
    l10n_ec_xml_fe_code = fields.Char(
        "Código en Facturacion electronica",
        size=10,
        help="Indica el codigo usado en el xml de facturacion electronica que se envia al SRI, "
        "en caso de no estar configrado se tomara el codigo de impuesto normal",
    )

    def _get_tax_vals(self, company, tax_template_to_tax):
        """ This method generates a dictionnary of all the values for the tax that will be created.
        """
        self.ensure_one()
        val = super(AccountTaxTemplate, self)._get_tax_vals(
            company, tax_template_to_tax
        )
        val.update(
            {
                "l10n_ec_ats_code": self.l10n_ec_ats_code,
                "l10n_ec_xml_fe_code": self.l10n_ec_xml_fe_code,
            }
        )
        return val
