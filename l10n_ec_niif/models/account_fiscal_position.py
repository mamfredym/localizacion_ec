# -*- encoding: utf-8 -*-

from odoo import models, api, fields


class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'

    l10n_ec_no_account = fields.Boolean(u'Not Required to Keep Accounting?')
