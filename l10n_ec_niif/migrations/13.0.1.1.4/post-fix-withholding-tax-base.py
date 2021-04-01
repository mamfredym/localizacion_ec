import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    WithholdingLinesModel = env["l10n_ec.withhold.line"]
    withhold_iva_group = env.ref("l10n_ec_niif.tax_group_iva_withhold")
    retention_lines = WithholdingLinesModel.search(
        [
            ("invoice_id", "!=", False),
            ("withhold_id.state", "=", "done"),
            ("type", "=", "iva"),
            ("tax_id.tax_group_id", "=", withhold_iva_group.id),
        ]
    )
    for line in retention_lines:
        line.write(
            {
                "base_amount": line.invoice_id.l10n_ec_iva,
                "base_amount_currency": line.invoice_id.currency_id.compute(
                    line.invoice_id.l10n_ec_iva, line.invoice_id.currency_id
                ),
            }
        )
