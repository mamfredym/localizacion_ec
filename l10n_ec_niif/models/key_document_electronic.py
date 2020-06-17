# -*- encoding: utf-8 -*-

import os
import time

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _
from odoo.exceptions import except_orm, Warning, ValidationError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF


class res_company(models.Model):

    _inherit = 'res.company'

    @api.model
    def date_expire_send_mail(self):
        #expiration_dates = False
        keys_expired = self.env['sri.key.type'].search([])
        notification = []
        company = self.env.user.company_id
        authorization_days = company.authorization_expired_days
        if authorization_days <= 0:
            authorization_days = 20
        for key in keys_expired:
            expiration_date = key.expiration_date
            tdelta = expiration_date - datetime.now()
            days = round(tdelta.days + (tdelta.seconds / 86400.0), 0)
            # si no esta configurado, tomar 20 dias por defecto
            if days <= 20:
                notification.append("Nombre: " + key.name)
                notification.append("Fecha expiracion: " + key.expiration_date)
                notification.append("La llave expira en " + str(days) + " dias")
            else:
                notification.append("Nombre: " + key.name)
                notification.append("Fecha expiracion: " + key.expiration_date)
                notification.append("La llave ya expiro")
        return notification


res_company()
