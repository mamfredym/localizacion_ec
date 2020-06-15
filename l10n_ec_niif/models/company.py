# Part of Odoo. See LICENSE file for full copyright and licensing details.
import os

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.onchange('country_id')
    def onchange_country(self):
        """ Ecuadorian companies use round_globally as tax_calculation_rounding_method """
        for rec in self.filtered(lambda x: x.country_id == self.env.ref('base.ec')):
            rec.tax_calculation_rounding_method = 'round_globally'

    def _localization_use_documents(self):
        """ Ecuadorian localization use documents """
        self.ensure_one()
        return True if self.country_id == self.env.ref('base.ec') else super()._localization_use_documents()

    l10n_ec_consumidor_final_limit = fields.Float(
        string="Invoice Sales Limit Final Consumer", default=200.0)

    l10n_ec_withhold_sale_iva_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales IVA Account',
        required=False)

    l10n_ec_withhold_sale_iva_tag_id = fields.Many2one(
        comodel_name='account.account.tag',
        string='Withhold Sales IVA Account Tag',
        required=False)

    l10n_ec_withhold_sale_rent_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales Rent Account',
        required=False)

    l10n_ec_withhold_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Withhold Journal',
        required=False)
    # campos para facturacion electronica
    type_environment = fields.Selection([
        ('test', 'Pruebas'),
        ('production', 'Producción'),
    ], string='Tipo de Ambiente de Documentos Electronicos', default='test', )
    type_conection_sri = fields.Selection([
        ('online', 'On-Line'),
        ('offline', 'Off-Line'),
    ], string='Tipo de conexion con SRI', default='offline')
    key_type_id = fields.Many2one('sri.key.type', 'Tipo de Llave', ondelete="restrict")
    ws_receipt_test = fields.Char('URL del WS de Pruebas de SRI para Recepción de Documentos',
        default='https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl')
    ws_auth_test = fields.Char('URL del WS de Pruebas de SRI para Autorización de Documentos',
        default='https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl')
    ws_receipt_production = fields.Char('URL del WS de Producción de SRI para Recepción de Documentos',
        default='https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl')
    ws_auth_production = fields.Char('URL del WS de Producción SRI para Autorización de Documentos',
        default='https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl')
    electronic_invoice = fields.Boolean('Autorizado Facturas?')
    electronic_delivery_note = fields.Boolean('Autorizado Guías de Remisión?')
    electronic_withhold = fields.Boolean('Autorizado Retenciones?')
    electronic_credit_note = fields.Boolean('Autorizado Notas de Crédito?')
    electronic_debit_note = fields.Boolean('Autorizado Notas de Débito?')
    electronic_liquidation = fields.Boolean('Autorizado Liquidacion de compras?')
    invoice_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Facturas', domain=[('document_type', '=', 'invoice')])
    delivery_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Guias de remision', domain=[('document_type', '=', 'delivery_note')])
    withholding_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Retencion', domain=[('document_type', '=', 'withholding')])
    credit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Credito', domain=[('document_type', '=', 'credit_note')])
    debit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Debito', domain=[('document_type', '=', 'debit_note')])
    liquidation_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Liquidacion de compras', domain=[('document_type', '=', 'liquidation')])
    # campo para la imagen que va en los documentos electronicos
    electronic_logo = fields.Binary('Logo de Documentos electrónicos')
    max_intentos = fields.Integer('Intentos máximos de autorización')
    ws_timeout = fields.Integer('Timeout Web Service', default=30)
    cron_process = fields.Integer('Number Documents Process in Cron', default=100)
    path_files_electronic = fields.Char('Ruta para Documentos Electronicos',
                                        default=lambda self: self._get_default_path_files_electronic())
    send_mail_from = fields.Datetime('Enviar Mail desde', default=lambda self: fields.Datetime.now())
    send_mail_invoice = fields.Boolean('Facturas electronicas?', default=True, )
    send_mail_credit_note = fields.Boolean('Notas de Crédito?', default=True)
    send_mail_debit_note = fields.Boolean('Notas de Débito?', default=True)
    send_mail_remision = fields.Boolean('Guía de Remisión?', default=True)
    send_mail_retention = fields.Boolean('Retenciones?', default=True)
    send_mail_liquidation = fields.Boolean('Liquidacion de compras?', default=True)
    create_login_for_partners = fields.Boolean('Crear Usuario para portal?', default=False, )
    print_ride_main_code = fields.Boolean('Imprimir Codigo Principal?', default=True)
    print_ride_aux_code = fields.Boolean('Imprimir Codigo Auxiliar?', default=False)
    print_ride_detail1 = fields.Boolean('Imprimir Detalle Adicional 1?', default=True)
    print_ride_detail2 = fields.Boolean('Imprimir Detalle Adicional 2?', default=False)
    print_ride_detail3 = fields.Boolean('Imprimir Detalle Adicional 3?', default=False)
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment.method', string=u'S.R.I Payment Method')

    @api.constrains('path_files_electronic', )
    def _check_path_files_electronic(self):
        # validar que se puedan crear archivos en el directorio especificado
        # TODO: encontrar una mejor manera de acceder a los permisos de un directorio
        if self.path_files_electronic:
            # si el directorio no existe, crearlo
            if not os.path.isdir(self.path_files_electronic):
                try:
                    os.makedirs(self.path_files_electronic)
                except IOError:
                    raise ValidationError(
                        "Error al acceder a la ruta configurada para los documentos electronicos, por favor verifique los permisos de acceso")
            # crear un archivo temporal para hacer la prueba
            try:
                f_name_temp = os.path.join(self.path_files_electronic, 'test.txt')
                f_temp = open(f_name_temp, "w")
                f_temp.close()
                os.remove(f_name_temp)
            except IOError:
                raise ValidationError(
                    "Error al acceder a la ruta configurada para los documentos electronicos, por favor verifique los permisos de acceso")

    @api.model
    def _get_default_path_files_electronic(self):
        # obtener la ruta del archivo de ejecucion del server
        source_folder = "files_electronics"
        home_name = "HOME"
        if os.name in ('os2', 'nt'):
            home_name = "USERPROFILE"
        path_files_electronic = os.path.abspath(os.path.join(os.environ[home_name], source_folder))
        # obtener el parent del directorio, xq el archivo se ejecuta en server/bin
        # crear una carpeta files_electronics en server/files_electronics
        if not os.path.isdir(path_files_electronic):
            os.makedirs(path_files_electronic)
        return path_files_electronic

    @api.model
    def get_contribuyente_data(self, date=None):
        sri_resolution_model = self.env['l10n_ec.sri.company.resolution']
        if not date:
            date = fields.Date.context_today(self)
        sri_resolution_recs = sri_resolution_model.search([('date_from', '<=', date)])
        sri_resolution_rec = sri_resolution_model.browse()
        for sri_resolution in sri_resolution_recs:
            if not sri_resolution.date_to or sri_resolution.date_to >= date:
                sri_resolution_rec = sri_resolution
        return sri_resolution_rec and sri_resolution_rec.resolution or '000'

