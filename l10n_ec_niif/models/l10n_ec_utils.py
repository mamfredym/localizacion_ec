from odoo import models, api, fields, tools


class L10necUtils(models.AbstractModel):
    _name = 'l10n_ec.utils'
    _description = 'Utilities miscellaneous'

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
