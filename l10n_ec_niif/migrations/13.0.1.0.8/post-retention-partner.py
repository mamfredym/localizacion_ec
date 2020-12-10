import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    WithholdingModel = env["l10n_ec.withhold"]
    all_company = env["res.company"].search([])
    for company in all_company:
        withholding_recs = WithholdingModel.search(
            [("company_id", "=", company.id), ("type", "=", "sale"), ("state", "=", "done"), ("move_id", "!=", False)]
        )
        try:
            for withholding in withholding_recs:
                for line in withholding.move_id.line_ids:
                    if line.account_internal_type in ("receivable", "payable"):
                        if not line.partner_id:
                            line.write({"partner_id": withholding.commercial_partner_id.id})
                    elif line.partner_id:
                        line.write({"partner_id": False})
        except Exception as ex:
            _logger.warning(tools.ustr(ex))
