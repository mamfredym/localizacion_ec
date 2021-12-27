from . import controllers
from . import models
from . import wizard
from . import tests

from odoo import api, SUPERUSER_ID
from odoo.addons import account

native_auto_install_l10n = account._auto_install_l10n


def update_payment_term_type(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    payment_term_inmediate = env.ref("account.account_payment_term_immediate", False)
    if payment_term_inmediate:
        payment_term_inmediate.write({"l10n_ec_sri_type": "contado"})


def _auto_install_l10n_ec(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    country_code = env.company.country_id.code
    if country_code:
        module_list = []
        if country_code != "EC":
            return native_auto_install_l10n(cr, registry)
        else:
            module_list.append("l10n_ec_niif")
            module_ids = env["ir.module.module"].search([("name", "in", module_list), ("state", "=", "uninstalled")])
            module_ids.sudo().button_install()


account._auto_install_l10n = _auto_install_l10n_ec
