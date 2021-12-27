import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    payment_term_inmediate = env.ref("account.account_payment_term_immediate", False)
    if payment_term_inmediate:
        payment_term_inmediate.write({"l10n_ec_sri_type": "contado"})
