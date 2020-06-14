# -*- encoding: utf-8 -*-

from odoo import models, api, fields
import odoo.addons.decimal_precision as dp
from odoo.tools.translate import _


class sri_error_code(models.Model):

    _name = 'sri.error.code'
    _description = 'Errores SRI'

    code = fields.Char(u'Código', size=256, required=True, help=u"",)
    name = fields.Char(u'Descripción', size=256, required=True, help=u"",)
    solution = fields.Char(u'Posible Solucion', size=256,
                           required=True, help=u"",)
    raise_error = fields.Boolean(u'Mostrar Error al Usuario?', readonly=False,
                                 help=u"Se enviara la descripcion del error al usuario en el momento que se aprueba el documento",)
    no_resend = fields.Boolean(u'No Reenviar?', readonly=False,
                               help=u"Usar para que no se trate de reenviar el documento cuando devuelve este codigo",)
    change_key = fields.Boolean(u'Cambiar Clave?', readonly=False,
                                help=u"Es necesario regenerar la clave cuando se recibe este error",)

    @api.multi
    def name_get(self):
        res = []
        for element in self:
            name = u"%s %s" % (
                element.code and "[" + element.code + "]" or '', element.name)
            res.append((element.id, name))
        return res


sri_error_code()
