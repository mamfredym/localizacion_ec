import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tax_group_iva_0 = env.ref("l10n_ec_niif.tax_group_iva_0")
    tax_list = [
        "tax_423_iva",
        "tax_424_iva",
        "tax_417_iva",
        "tax_418_iva",
        "tax_526_iva",
        "tax_527_iva",
    ]
    all_company = env["res.company"].search([])
    for company in all_company:
        for tax_idxml in tax_list:
            try:
                tax_id_xml = f"l10n_ec_niif.{company.id}_{tax_idxml}"
                current_tax = env.ref(tax_id_xml, False)
                if not current_tax:
                    continue
                current_tax.write({"tax_group_id": tax_group_iva_0.id})
            except Exception as ex:
                _logger.warning(tools.ustr(ex))
