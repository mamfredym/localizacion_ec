import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    TaxRepartition = env["account.tax.repartition.line"]
    old_account_id_xml = "101050201"
    new_account_xml = "201070106"
    all_company = env["res.company"].search([])
    for company in all_company:
        old_account = env.ref(f"l10n_ec_niif.{company.id}_{old_account_id_xml}", False)
        new_account = env.ref(f"l10n_ec_niif.{company.id}_{new_account_xml}", False)
        if not old_account or not new_account:
            _logger.warning(
                "Accounts: %s, %s are not found for update tax repartition lines on company %s",
                old_account_id_xml,
                new_account_xml,
                company.name,
            )
            continue
        tax_repartition = TaxRepartition.search(
            [
                ("company_id", "=", company.id),
                ("account_id", "=", old_account.id),
            ]
        )
        try:
            tax_repartition.write({"account_id": new_account.id})
        except Exception as ex:
            _logger.warning(tools.ustr(ex))
