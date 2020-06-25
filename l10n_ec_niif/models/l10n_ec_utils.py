from odoo import api, fields, models, tools


class L10necUtils(models.AbstractModel):
    _name = "l10n_ec.utils"
    _description = "Utilities miscellaneous"

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
        res = "SI"
        if fiscal_position and fiscal_position.l10n_ec_no_account:
            res = "NO"
        return res

    def get_formato_date(self):
        return "%d/%m/%Y"

    def ensure_id(self, recordset):
        # Devolver el ID del registro, hay problemas en los onchange, que no se pasa el id
        # sino un NewID, pero el id de BD se guarda en la variable _origin.id
        # sin embargo en algunos casos la variable _origin no se pasa
        # asi que tratar de tomar el id correctamente
        record_id = recordset.id
        if hasattr(recordset, "_origin") and recordset._origin.id:
            record_id = recordset._origin.id
        if isinstance(record_id, models.NewId):
            record_id = False
        return record_id

    @api.model
    def _clean_str(self, string_to_reeplace, list_characters=None, separator=""):
        """
        Reemplaza caracteres por otros caracteres especificados en la lista
        @param string_to_reeplace:  string a la cual reemplazar caracteres
        @param list_characters:  Lista de tuplas con dos elementos(elemento uno el caracter a reemplazar, elemento dos caracter que reemplazara al elemento uno)
        @return: string con los caracteres reemplazados
        """
        if not string_to_reeplace:
            return string_to_reeplace
        caracters = [".", ",", "-", "\a", "\b", "\f", "\n", "\r", "\t", "\v"]
        for c in caracters:
            string_to_reeplace = string_to_reeplace.replace(c, separator)
        if not list_characters:
            list_characters = [
                ("á", "a"),
                ("à", "a"),
                ("ä", "a"),
                ("â", "a"),
                ("Á", "A"),
                ("À", "A"),
                ("Ä", "A"),
                ("Â", "A"),
                ("é", "e"),
                ("è", "e"),
                ("ë", "e"),
                ("ê", "e"),
                ("É", "E"),
                ("È", "E"),
                ("Ë", "E"),
                ("Ê", "E"),
                ("í", "i"),
                ("ì", "i"),
                ("ï", "i"),
                ("î", "i"),
                ("Í", "I"),
                ("Ì", "I"),
                ("Ï", "I"),
                ("Î", "I"),
                ("ó", "o"),
                ("ò", "o"),
                ("ö", "o"),
                ("ô", "o"),
                ("Ó", "O"),
                ("Ò", "O"),
                ("Ö", "O"),
                ("Ô", "O"),
                ("ú", "u"),
                ("ù", "u"),
                ("ü", "u"),
                ("û", "u"),
                ("Ú", "U"),
                ("Ù", "U"),
                ("Ü", "U"),
                ("Û", "U"),
                ("ñ", "n"),
                ("Ñ", "N"),
                ("/", "-"),
                ("&", "Y"),
                ("º", ""),
                ("´", ""),
            ]
        for character in list_characters:
            string_to_reeplace = string_to_reeplace.replace(character[0], character[1])
        SPACE = " "
        codigo_ascii = False
        # en range el ultimo numero no es inclusivo asi que agregarle uno mas
        # espacio en blanco
        range_ascii = [32]
        # numeros
        range_ascii += list(range(48, 57 + 1))
        # letras mayusculas
        range_ascii += list(range(65, 90 + 1))
        # letras minusculas
        range_ascii += list(range(97, 122 + 1))
        for c in string_to_reeplace:
            codigo_ascii = False
            try:
                codigo_ascii = ord(c)
            except TypeError:
                codigo_ascii = False
            if codigo_ascii:
                # si no esta dentro del rang ascii reemplazar por un espacio
                if codigo_ascii not in range_ascii:
                    string_to_reeplace = string_to_reeplace.replace(c, SPACE)
            # si no tengo codigo ascii, posiblemente dio error en la conversion
            else:
                string_to_reeplace = string_to_reeplace.replace(c, SPACE)
        return "".join(string_to_reeplace.splitlines())
