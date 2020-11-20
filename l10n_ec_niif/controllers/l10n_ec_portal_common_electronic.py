from datetime import datetime

from odoo.osv.expression import OR
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF, DEFAULT_SERVER_DATETIME_FORMAT as DTF

from odoo.addons.portal.controllers.portal import CustomerPortal


class PortalElectronicCommon(CustomerPortal):
    field_document_number = None

    def is_date_valid(self, date_value):
        """
        Verificar si es una fecha valida, en formato de fecha o en formato de fecha y hora
        """
        is_valid = True
        try:
            datetime.strptime(date_value.strip(), DF)
        except Exception:
            try:
                datetime.strptime(date_value.strip(), DTF)
            except Exception:
                is_valid = False
        return is_valid

    def search_validate(self, field_name, field_value):
        error = dict()
        error_message = []
        # Validation
        if field_name == "fecha_auth" and field_value:
            if not self.is_date_valid(field_value):
                error[field_name] = "error"
                error_message.append("Fecha no Valida, se espera formato: yyyy-mm-dd")
        return error, error_message

    def get_search_domain(self, search, search_in):
        # search
        search_domain = []
        if search and search_in:
            search_domain = []
            if search_in in ("numero", "all") and self.field_document_number:
                search_domain = OR([search_domain, [(self.field_document_number, "ilike", search)]])
            if search_in in ("fecha_auth", "all") and self.is_date_valid(search):
                search_domain = OR([search_domain, [("l10n_ec_authorization_date", "=", search)]])
            if search_in in ("clave", "all"):
                search_domain = OR([search_domain, [("l10n_ec_xml_key", "ilike", search)]])
        return search_domain

    def get_searchbar_sortings(self):
        searchbar_sortings = {
            "fecha_auth": {
                "label": "Fecha Autorización(Recientes)",
                "order": "l10n_ec_authorization_date desc",
            },
            "fecha_auth_asc": {
                "label": "Fecha Autorización(Antiguas)",
                "order": "l10n_ec_authorization_date",
            },
        }
        if self.field_document_number:
            searchbar_sortings.update(
                {
                    "numero": {
                        "label": "Número de Documento(Recientes)",
                        "order": f"{self.field_document_number} desc",
                    },
                    "numero_desc": {
                        "label": "Número de Documento(Antiguos)",
                        "order": self.field_document_number,
                    },
                }
            )
        return searchbar_sortings

    def get_searchbar_inputs(self):
        searchbar_inputs = {
            "fecha_auth": {
                "input": "fecha_auth",
                "label": "Fecha de Autorización(yyyy-mm-dd)",
            },
            "clave": {"input": "clave", "label": "Clave de Acceso"},
            "todo": {"input": "all", "label": "Todo"},
        }
        if self.field_document_number:
            searchbar_inputs["numero"] = {
                "input": "numero",
                "label": "Numero de Documento",
            }
        return searchbar_inputs
