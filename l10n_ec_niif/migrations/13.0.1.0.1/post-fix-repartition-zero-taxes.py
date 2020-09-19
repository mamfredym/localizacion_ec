from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tax_model = env["account.tax"]
    repartition_line = env["account.tax.repartition.line"]
    tax_group_iva = env.ref("l10n_ec_niif.tax_group_iva")
    tax_group_iva_withhold = env.ref("l10n_ec_niif.tax_group_iva_withhold")
    tax_group_renta_withhold = env.ref("l10n_ec_niif.tax_group_renta_withhold")
    groups = tax_group_iva + tax_group_iva_withhold + tax_group_renta_withhold
    zero_taxes = tax_model.search([("amount", "=", 0), ("tax_group_id", "in", groups.ids)])
    for tax in zero_taxes:
        if not tax.invoice_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax"):
            repartition_line.create(
                {
                    "repartition_type": "tax",
                    "invoice_tax_id": tax.id,
                    "company_id": tax.company_id.id,
                    "factor_percent": 0.0,
                }
            )
        if not tax.refund_repartition_line_ids.filtered(lambda x: x.repartition_type == "tax"):
            repartition_line.create(
                {
                    "repartition_type": "tax",
                    "refund_tax_id": tax.id,
                    "company_id": tax.company_id.id,
                    "factor_percent": 0.0,
                }
            )
