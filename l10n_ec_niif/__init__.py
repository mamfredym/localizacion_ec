from . import models

from odoo import api, SUPERUSER_ID
from odoo.addons import account

native_auto_install_l10n = account._auto_install_l10n

def _auto_install_l10n_ec(cr, registry):
    #check the country of the main company (only) and eventually load some module needed in that country
    env = api.Environment(cr, SUPERUSER_ID, {})
    country_code = env.company.country_id.code
    if country_code:
        #auto install localization module(s) if available
        module_list = []
        if country_code != 'EC':
            return native_auto_install_l10n(cr, registry)
        else:
            module_list.append('l10n_ec_niif')
            module_ids = env['ir.module.module'].search([('name', 'in', module_list), ('state', '=', 'uninstalled')])
            module_ids.sudo().button_install()

account._auto_install_l10n = _auto_install_l10n_ec