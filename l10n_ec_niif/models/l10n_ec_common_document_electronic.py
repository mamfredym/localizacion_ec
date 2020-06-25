import base64
from xml.etree.ElementTree import SubElement

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF


class L10nEcCommonDocumentElectronic(models.AbstractModel):
    _name = "ln10_ec.common.document.electronic"
    _description = "Abstract Class for electronic documents"

    ln10_ec_electronic_authorization = fields.Char(
        "Autorizacion Electrónica", size=49, copy=False, index=True, readonly=True
    )
    ln10_ec_xml_data_id = fields.Many2one(
        "sri.xml.data",
        "XML electronico",
        copy=False,
        index=True,
        auto_join=True,
        readonly=True,
    )
    ln10_ec_xml_key = fields.Char(
        "Clave de acceso", size=49, copy=False, index=True, readonly=True
    )
    ln10_ec_authorization_date = fields.Datetime(
        "Fecha de Autorización", copy=False, index=True, readonly=True
    )

    @api.model
    def get_identification_type_partner(self, partner):
        # codigos son tomados de la ficha tecnica del SRI, tabla 7
        # pasar por defecto consumidor final
        tipoIdentificacionComprador = "07"
        if partner.l10n_ec_type_sri == "Ruc":
            tipoIdentificacionComprador = "04"
        elif partner.l10n_ec_type_sri == "Cedula":
            tipoIdentificacionComprador = "05"
        elif partner.l10n_ec_type_sri == "Pasaporte":
            tipoIdentificacionComprador = "06"
        return tipoIdentificacionComprador

    def _prepare_l10n_ec_sri_xml_values(self, l10n_ec_type_conection_sri):
        return {"l10n_ec_type_conection_sri": l10n_ec_type_conection_sri}

    def get_printed_report_name_l10n_ec(self):
        # funcion solo usada para ser llamada de manera externa
        # ya que no se puede llamar a la funcion declarada como privada
        return self._get_report_base_filename()

    def l10n_ec_get_attachments_electronic(self):
        """
        :return: An ir.attachment recordset
        """
        self.ensure_one()
        if not self.ln10_ec_xml_key:
            return []
        domain = [
            ("res_id", "=", self.id),
            ("res_model", "=", self._name),
            ("name", "=", "%s.xml" % self.get_printed_report_name_l10n_ec()),
            ("description", "=", self.ln10_ec_xml_key),
        ]
        return self.env["ir.attachment"].search(domain)

    def l10n_ec_action_create_attachments_electronic(self, file_data=None):
        """
        :return: An ir.attachment recordset
        """
        self.ensure_one()
        ctx = self.env.context.copy()
        # borrar el default_type de facturas
        ctx.pop("default_type", False)
        AttachmentModel = self.env["ir.attachment"].with_context(ctx)
        attachment = AttachmentModel.browse()
        if self.ln10_ec_xml_key and self.ln10_ec_xml_data_id:
            attachment = self.l10n_ec_get_attachments_electronic()
            if not attachment:
                if file_data is None:
                    file_data = (
                        self.ln10_ec_xml_data_id._action_create_file_authorized()
                    )
                file_name = self.get_printed_report_name_l10n_ec()
                if file_data:
                    attachment = AttachmentModel.create(
                        {
                            "name": "%s.xml" % file_name,
                            "res_id": self.id,
                            "res_model": self._name,
                            "datas": base64.encodebytes(file_data.encode()),
                            "store_fname": "%s.xml" % file_name,
                            "description": self.ln10_ec_xml_key,
                        }
                    )
        return attachment

    def l10n_ec_action_update_electronic_authorization(
        self, numeroAutorizacion, ln10_ec_authorization_date
    ):
        self.write(
            {
                "ln10_ec_electronic_authorization": str(numeroAutorizacion),
                "ln10_ec_authorization_date": ln10_ec_authorization_date.strftime(DTF),
            }
        )

    def l10n_ec_action_sent_mail_electronic(self):
        # funcion debe ser reemplazada en cada clase heredada
        # es usada para envio del mail al cliente
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_action_sent_mail_electronic en su clase heredada"
        )

    def l10n_ec_get_document_code_sri(self):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe devolver el tipo de documento SRI que va en el xml electronico
        # 01 : Factura
        # 03 : Liquidacion de Compras
        # 04 : Nota de Credito
        # 05 : Nota de Debito
        # 06 : Guia de Remision
        # 07 : Comprobante de Retencion
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_get_document_code_sri en su clase heredada"
        )

    def l10n_ec_get_document_number(self):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe devolver el numero de documento
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_get_document_number en su clase heredada"
        )

    def l10n_ec_get_document_date(self):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe devolver la fecha de emision del documento
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_get_document_date en su clase heredada"
        )

    def l10n_ec_get_document_version_xml(self):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe devolver la version del xml que se debe usar
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_get_document_version_xml en su clase heredada"
        )

    def l10n_ec_get_document_filename_xml(self):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe devolver el nombre del archivo xml sin la extension
        # algo como: id, prefijo, secuencial
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_get_document_filename_xml en su clase heredada"
        )

    def l10n_ec_action_generate_xml_data(self, node_root):
        # funcion debe ser reemplazada en cada clase heredada
        # esta funcion debe crear la data del documento en el xml(node_root)
        raise UserError(
            "Debe reemplazar esta funcion l10n_ec_action_generate_xml_data en su clase heredada"
        )

    def _l10n_ec_get_info_aditional(self):
        # TODO: implementar modelo para informacion adicional
        info_data = []
        return info_data

    @api.model
    def l10n_ec_add_info_adicional(self, NodeRoot):
        util_model = self.env["l10n_ec.utils"]
        infoAdicional = SubElement(NodeRoot, "infoAdicional")
        info_data = self._l10n_ec_get_info_aditional()
        if not info_data:
            info_data = [{"name": "OtroCampo", "description": "Otra Informacion",}]
        for line in info_data:
            campoAdicional = SubElement(infoAdicional, "campoAdicional")
            campoAdicional.set(
                "nombre", util_model._clean_str(line.get("name", "OtroCampo"))
            )
            campoAdicional.text = util_model._clean_str(
                line.get("description", "Otra Informacion")
            )
        return True
