import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    all_company = env["res.company"].search([])
    all_taxes = env["account.tax.template"].search([])
    external_id_data = all_taxes.get_external_id()
    for company in all_company:
        for tax_template in all_taxes:
            tax_idxml = external_id_data.get(tax_template.id) or ""
            try:
                parts = tax_idxml.split(".")
                module_name = "l10n_ec_niif"
                if len(parts) > 1:
                    module_name = parts[0]
                    tax_idxml = "_".join(parts[1:])
                tax_id_xml = f"{module_name}.{company.id}_{tax_idxml}"
                current_tax = env.ref(tax_id_xml, False)
                if not current_tax:
                    continue
                current_tax.write({"name": tax_template.name})
            except Exception as ex:
                _logger.warning(tools.ustr(ex))
