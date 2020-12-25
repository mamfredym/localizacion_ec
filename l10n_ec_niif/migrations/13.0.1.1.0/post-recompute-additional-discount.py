import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    InvoiceModel = env["account.move"]
    all_company = env["res.company"].search([])
    for company in all_company:
        invoice_recs = InvoiceModel.search(
            [("company_id", "=", company.id), ("type", "in", ["out_invoice", "out_refund"]), ("state", "=", "posted")]
        )
        try:
            invoice_recs.l10n_ec_asign_discount_to_lines()
        except Exception as ex:
            _logger.warning(tools.ustr(ex))
