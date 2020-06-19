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
    l10n_ec_type_environment = fields.Selection([
        ('test', 'Pruebas'),
        ('production', 'Producción'),
    ], string='Tipo de Ambiente de Documentos Electronicos', default='test', )
    l10n_ec_type_conection_sri = fields.Selection([
        ('online', 'On-Line'),
        ('offline', 'Off-Line'),
    ], string='Tipo de conexion con SRI', default='offline')
    l10n_ec_key_type_id = fields.Many2one('sri.key.type', 'Tipo de Llave', ondelete="restrict")
    l10n_ec_ws_receipt_test = fields.Char('URL del WS de Pruebas de SRI para Recepción de Documentos',
        default='https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl')
    l10n_ec_ws_auth_test = fields.Char('URL del WS de Pruebas de SRI para Autorización de Documentos',
        default='https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl')
    l10n_ec_ws_receipt_production = fields.Char('URL del WS de Producción de SRI para Recepción de Documentos',
        default='https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl')
    l10n_ec_ws_auth_production = fields.Char('URL del WS de Producción SRI para Autorización de Documentos',
        default='https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl')
    l10n_ec_electronic_invoice = fields.Boolean('Autorizado Facturas?')
    l10n_ec_electronic_withhold = fields.Boolean('Autorizado Retenciones?')
    l10n_ec_electronic_credit_note = fields.Boolean('Autorizado Notas de Crédito?')
    l10n_ec_electronic_debit_note = fields.Boolean('Autorizado Notas de Débito?')
    l10n_ec_electronic_liquidation = fields.Boolean('Autorizado Liquidacion de compras?')
    l10n_ec_invoice_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Facturas', domain=[('document_type', '=', 'invoice')])
    l10n_ec_withholding_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Retencion', domain=[('document_type', '=', 'withholding')])
    l10n_ec_credit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Credito', domain=[('document_type', '=', 'credit_note')])
    l10n_ec_debit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Debito', domain=[('document_type', '=', 'debit_note')])
    l10n_ec_liquidation_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Liquidacion de compras', domain=[('document_type', '=', 'liquidation')])
    # campo para la imagen que va en los documentos electronicos
    l10n_ec_electronic_logo = fields.Binary('Logo de Documentos electrónicos')
    l10n_ec_max_intentos = fields.Integer('Intentos máximos de autorización')
    l10n_ec_ws_timeout = fields.Integer('Timeout Web Service', default=30)
    l10n_ec_cron_process = fields.Integer('Number Documents Process in Cron', default=100)
    l10n_ec_path_files_electronic = fields.Char('Ruta para Documentos Electronicos',
                                        default=lambda self: self._get_default_l10n_ec_path_files_electronic())
    l10n_ec_send_mail_from = fields.Datetime('Enviar Mail desde', default=lambda self: fields.Datetime.now())
    l10n_ec_send_mail_invoice = fields.Boolean('Facturas electronicas?', default=True, )
    l10n_ec_send_mail_credit_note = fields.Boolean('Notas de Crédito?', default=True)
    l10n_ec_send_mail_debit_note = fields.Boolean('Notas de Débito?', default=True)
    l10n_ec_send_mail_retention = fields.Boolean('Retenciones?', default=True)
    l10n_ec_send_mail_liquidation = fields.Boolean('Liquidacion de compras?', default=True)
    l10n_ec_create_login_for_partners = fields.Boolean('Crear Usuario para portal?', default=False, )
    l10n_ec_print_ride_main_code = fields.Boolean('Imprimir Codigo Principal?', default=True)
    l10n_ec_print_ride_aux_code = fields.Boolean('Imprimir Codigo Auxiliar?', default=False)
    l10n_ec_print_ride_detail1 = fields.Boolean('Imprimir Detalle Adicional 1?', default=True)
    l10n_ec_print_ride_detail2 = fields.Boolean('Imprimir Detalle Adicional 2?', default=False)
    l10n_ec_print_ride_detail3 = fields.Boolean('Imprimir Detalle Adicional 3?', default=False)
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment.method', string=u'S.R.I Payment Method')

    @api.constrains('l10n_ec_path_files_electronic', )
    def _check_l10n_ec_path_files_electronic(self):
        # validar que se puedan crear archivos en el directorio especificado
        # TODO: encontrar una mejor manera de acceder a los permisos de un directorio
        if self.l10n_ec_path_files_electronic:
            # si el directorio no existe, crearlo
            if not os.path.isdir(self.l10n_ec_path_files_electronic):
                try:
                    os.makedirs(self.l10n_ec_path_files_electronic)
                except IOError:
                    raise ValidationError(
                        "Error al acceder a la ruta configurada para los documentos electronicos, por favor verifique los permisos de acceso")
            # crear un archivo temporal para hacer la prueba
            try:
                f_name_temp = os.path.join(self.l10n_ec_path_files_electronic, 'test.txt')
                f_temp = open(f_name_temp, "w")
                f_temp.close()
                os.remove(f_name_temp)
            except IOError:
                raise ValidationError(
                    "Error al acceder a la ruta configurada para los documentos electronicos, por favor verifique los permisos de acceso")

    @api.model
    def _get_default_l10n_ec_path_files_electronic(self):
        # obtener la ruta del archivo de ejecucion del server
        source_folder = "files_electronics"
        home_name = "HOME"
        if os.name in ('os2', 'nt'):
            home_name = "USERPROFILE"
        l10n_ec_path_files_electronic = os.path.abspath(os.path.join(os.environ[home_name], source_folder))
        # obtener el parent del directorio, xq el archivo se ejecuta en server/bin
        # crear una carpeta files_electronics en server/files_electronics
        if not os.path.isdir(l10n_ec_path_files_electronic):
            os.makedirs(l10n_ec_path_files_electronic)
        return l10n_ec_path_files_electronic

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

