from odoo import models, api, fields, tools


class L10necUtils(models.AbstractModel):
    _name = 'l10n_ec.utils'
    _description = 'Utilities miscellaneous'

    @api.model
    def indent(self, elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    @api.model
    def formato_numero(self, valor, decimales=2):
        if isinstance(valor, (int, float)):
            str_format = "{:." + str(decimales) + "f}"
            return str_format.format(valor)
        else:
            return "0.00"

    @api.model
    def get_obligado_contabilidad(self, fiscal_position=None):
        res = 'SI'
        if fiscal_position and fiscal_position.l10n_ec_no_account:
            res = 'NO'
        return res

    def get_formato_date(self):
        return '%d/%m/%Y'

    def ensure_id(self, recordset):
        # Devolver el ID del registro, hay problemas en los onchange, que no se pasa el id
        # sino un NewID, pero el id de BD se guarda en la variable _origin.id
        # sin embargo en algunos casos la variable _origin no se pasa
        # asi que tratar de tomar el id correctamente
        record_id = recordset.id
        if hasattr(recordset, '_origin') and recordset._origin.id:
            record_id = recordset._origin.id
        if isinstance(record_id, models.NewId):
            record_id = False
        return record_id
