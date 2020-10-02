import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    TaxModel = env["account.tax"]
    withhold_iva_group = env.ref("l10n_ec_niif.tax_group_iva_withhold", False)
    withhold_rent_group = env.ref("l10n_ec_niif.tax_group_renta_withhold", False)
    tax_group_ids = []
    if withhold_iva_group:
        tax_group_ids.append(withhold_iva_group.id)
    if withhold_rent_group:
        tax_group_ids.append(withhold_rent_group.id)
    all_company = env["res.company"].search([])
    for company in all_company:
        tax_withholding = TaxModel.search([("company_id", "=", company.id), ("tax_group_id", "in", tax_group_ids)])
        try:
            tax_withholding._l10n_ec_action_create_tax_for_withholding()
        except Exception as ex:
            _logger.warning(tools.ustr(ex))
