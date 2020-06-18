import base64
from xml.etree.ElementTree import SubElement

from odoo import models, api, fields
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF


class L10nEcCommonDocumentElectronic(models.AbstractModel):
    _name = 'ln10_ec.common.document.electronic'
    _description = 'Abstract Class for electronic documents'

    ln10_ec_electronic_authorization = fields.Char('Autorizacion Electrónica',
                                           size=49, copy=False, index=True)
    ln10_ec_xml_data_id = fields.Many2one('sri.xml.data', 'XML electronico',
                                  copy=False, index=True, auto_join=True)
    ln10_ec_xml_key = fields.Char('Clave de acceso',
                          size=49, copy=False, index=True)
    ln10_ec_authorization_date = fields.Datetime('Fecha de Autorización',
                                         copy=False, index=True)

    def _prepare_l10n_ec_sri_xml_values(self, l10n_ec_type_conection_sri):
        return {
            'l10n_ec_type_conection_sri': l10n_ec_type_conection_sri
        }

    def get_printed_report_name_l10n_ec(self):
        # funcion solo usada para ser llamada de manera externa
        # ya que no se puede llamar a la funcion declarada como privada
        return self._get_report_base_filename()

    def get_attachments(self):
        '''
        :return: An ir.attachment recordset
        '''
        self.ensure_one()
        if not self.ln10_ec_xml_key:
            return []
        domain = [
            ('res_id', '=', self.id),
            ('res_model', '=', self._name),
            ('name', '=', "%s.xml" % self.get_printed_report_name_l10n_ec()),
            ('description', '=', self.ln10_ec_xml_key),
        ]
        return self.env['ir.attachment'].search(domain)

    def create_attachments(self):
        '''
        :return: An ir.attachment recordset
        '''
        self.ensure_one()
        ctx = self.env.context.copy()
        # borrar el default_type de facturas
        ctx.pop('default_type', False)
        AttachmentModel = self.env['ir.attachment'].with_context(ctx)
        attachment = AttachmentModel.browse()
        if self.ln10_ec_xml_key and self.ln10_ec_xml_data_id:
            attachment = self.get_attachments()
            if not attachment:
                try:
                    file_data = self.ln10_ec_xml_data_id.get_file('file_authorized')
                except:
                    file_data = ""
                file_name = self.get_printed_report_name_l10n_ec()
                if file_data:
                    attachment = AttachmentModel.create({
                        'name': "%s.xml" % file_name,
                        'res_id': self.id,
                        'res_model': self._name,
                        'datas': base64.encodebytes(file_data.encode()),
                        'datas_fname': "%s.xml" % file_name,
                        'description': self.ln10_ec_xml_key,
                    })
        return attachment

    def action_update_authorization_data(self, numeroAutorizacion, ln10_ec_authorization_date):
        self.write({
            'ln10_ec_electronic_authorization': str(numeroAutorizacion),
            'ln10_ec_authorization_date': ln10_ec_authorization_date.strftime(DTF),
        })

    def action_sent_mail(self):
        # funcion usada para envio del mail al cliente, mdelos deben reemplazarla
        return True

    def _get_info_aditional(self, field_name, record_id):
        SQL = """SELECT info.name,
                        info.description
                    FROM xml_info_aditional info
                    WHERE info.""" + field_name + """ = %(record_id)s
            """
        self.env.cr.execute(SQL, {
            'field_name': field_name,
            'record_id': record_id,
        })
        info_data = self.env.cr.dictfetchall()
        return info_data

    @api.model
    def add_info_adicional(self, infoAditionalNode, info_data):
        util_model = self.env['l10n_ec.utils']
        for line in info_data:
            campoAdicional = SubElement(infoAditionalNode, "campoAdicional")
            campoAdicional.set("nombre", util_model._clean_str(line.get("name", "OtroCampo")))
            campoAdicional.text = util_model._clean_str(line.get("description", "Otra Informacion"))
        return True
