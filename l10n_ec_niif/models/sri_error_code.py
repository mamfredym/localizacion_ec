from odoo import fields, models


class SriErrorCode(models.Model):

    _name = "sri.error.code"
    _description = "Errores SRI"

    code = fields.Char(
        "Código",
        size=256,
        required=True,
        help="",
    )
    name = fields.Char(
        "Descripción",
        size=256,
        required=True,
        help="",
    )
    solution = fields.Char(
        "Posible Solucion",
        size=256,
        required=True,
        help="",
    )
    raise_error = fields.Boolean(
        "Mostrar Error al Usuario?",
        readonly=False,
        help="Se enviara la descripcion del error al usuario en el momento que se aprueba el documento",
    )
    no_resend = fields.Boolean(
        "No Reenviar?",
        readonly=False,
        help="Usar para que no se trate de reenviar el documento cuando devuelve este codigo",
    )
    change_key = fields.Boolean(
        "Cambiar Clave?",
        readonly=False,
        help="Es necesario regenerar la clave cuando se recibe este error",
    )

    def name_get(self):
        res = []
        for element in self:
            name = "{} {}".format(
                element.code and "[" + element.code + "]" or "",
                element.name,
            )
            res.append((element.id, name))
        return res
