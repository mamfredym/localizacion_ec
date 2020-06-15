
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    l10n_ec_consumidor_final_limit = fields.Float(string="Invoice Sales Limit Final Consumer",
                                                  related="company_id.l10n_ec_consumidor_final_limit", readonly=False)

    l10n_ec_withhold_sale_iva_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales IVA Account',
        related="company_id.l10n_ec_withhold_sale_iva_account_id",
        readonly=False)

    l10n_ec_withhold_sale_iva_tag_id = fields.Many2one(
        comodel_name='account.account.tag',
        string='Withhold Sales IVA Account Tag',
        related="company_id.l10n_ec_withhold_sale_iva_tag_id",
        readonly=False)

    l10n_ec_withhold_sale_rent_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Withhold Sales Rent Account',
        related="company_id.l10n_ec_withhold_sale_rent_account_id",
        readonly=False)

    l10n_ec_withhold_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Withhold Journal',
        related="company_id.l10n_ec_withhold_journal_id",
        readonly=False)
    # configuracion para facturacion electronica
    type_environment = fields.Selection([
        ('test', 'Pruebas'),
        ('production', 'Producción'),
    ], string='Tipo de Ambiente de Documentos Electronicos', related='company_id.type_environment', readonly=False)
    type_conection_sri = fields.Selection([
        ('online', 'On-Line'),
        ('offline', 'Off-Line'),
    ], string=u'Tipo de conexion con SRI', related='company_id.type_conection_sri', readonly=False)
    key_type_id = fields.Many2one('sri.key.type', 'Tipo de Llave',
        related='company_id.key_type_id', readonly=False)
    ws_receipt_test = fields.Char('URL del WS de Pruebas de SRI para Recepción de Documentos',
        related='company_id.ws_receipt_test', readonly=False)
    ws_auth_test = fields.Char('URL del WS de Pruebas de SRI para Autorización de Documentos',
        related='company_id.ws_auth_test', readonly=False)
    ws_receipt_production = fields.Char('URL del WS de Producción de SRI para Recepción de Documentos',
        related='company_id.ws_receipt_production', readonly=False)
    ws_auth_production = fields.Char('URL del WS de Producción SRI para Autorización de Documentos',
        related='company_id.ws_auth_production', readonly=False)
    electronic_invoice = fields.Boolean('Autorizado Facturas?',
        related='company_id.electronic_invoice', readonly=False)
    electronic_delivery_note = fields.Boolean('Autorizado Guías de Remisión?',
        related='company_id.electronic_delivery_note', readonly=False)
    electronic_withhold = fields.Boolean('Autorizado Retenciones?',
        related='company_id.electronic_withhold', readonly=False)
    electronic_credit_note = fields.Boolean('Autorizado Notas de Crédito?',
        related='company_id.electronic_credit_note', readonly=False)
    electronic_debit_note = fields.Boolean('Autorizado Notas de Débito?',
        related='company_id.electronic_debit_note', readonly=False)
    electronic_liquidation = fields.Boolean('Autorizado Liquidacion de compras?',
        related='company_id.electronic_liquidation', readonly=False)
    # campo para la imagen que va en los documentos electronicos
    electronic_logo = fields.Binary('Logo de Documentos electrónicos',
        related='company_id.electronic_logo', readonly=False)
    max_intentos = fields.Integer('Intentos máximos de autorización',
        related='company_id.max_intentos', readonly=False)
    ws_timeout = fields.Integer('Timeout Web Service',
        related='company_id.ws_timeout', readonly=False)
    cron_process = fields.Integer('Number Documents Process in Cron',
        related='company_id.cron_process', readonly=False)
    path_files_electronic = fields.Char('Ruta para Documentos Electronicos',
        related='company_id.path_files_electronic', readonly=False)
    send_mail_from = fields.Datetime('Enviar Mail desde',
        related='company_id.send_mail_from', readonly=False)
    send_mail_invoice = fields.Boolean('Facturas electronicas?',
        related='company_id.send_mail_invoice', readonly=False)
    send_mail_credit_note = fields.Boolean('Notas de Crédito?',
        related='company_id.send_mail_credit_note', readonly=False)
    send_mail_debit_note = fields.Boolean('Notas de Débito?',
        related='company_id.send_mail_debit_note', readonly=False)
    send_mail_remision = fields.Boolean('Guía de Remisión?',
        related='company_id.send_mail_remision', readonly=False)
    send_mail_retention = fields.Boolean('Retenciones?',
        related='company_id.send_mail_retention', readonly=False)
    send_mail_liquidation = fields.Boolean('Retenciones?',
        related='company_id.send_mail_liquidation', readonly=False)
    create_login_for_partners = fields.Boolean('Crear Usuario para portal?',
        related='company_id.create_login_for_partners', readonly=False)
    invoice_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Facturas',
        domain=[('document_type', '=', 'invoice')],
        related='company_id.invoice_version_xml_id', readonly=False)
    delivery_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Guias de remision',
        domain=[('document_type', '=', 'delivery_note')],
        related='company_id.delivery_note_version_xml_id', readonly=False)
    withholding_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Retencion',
        domain=[('document_type', '=', 'withholding')],
        related='company_id.withholding_version_xml_id', readonly=False)
    credit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Credito',
        domain=[('document_type', '=', 'credit_note')],
        related='company_id.credit_note_version_xml_id', readonly=False)
    debit_note_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Nota de Debito',
        domain=[('document_type', '=', 'debit_note')],
        related='company_id.debit_note_version_xml_id', readonly=False)
    liquidation_version_xml_id = fields.Many2one('l10n_ec.xml.version',
        string='Version del XML Liquidacion de compras',
        domain=[('document_type', '=', 'liquidation')],
        related='company_id.liquidation_version_xml_id', readonly=False)
    print_ride_main_code = fields.Boolean('Imprimir Codigo Principal?',
        related='company_id.print_ride_main_code', readonly=False)
    print_ride_aux_code = fields.Boolean('Imprimir Codigo Auxiliar?',
        related='company_id.print_ride_aux_code', readonly=False)
    print_ride_detail1 = fields.Boolean('Imprimir Detalle Adicional 1?',
        related='company_id.print_ride_detail1', readonly=False)
    print_ride_detail2 = fields.Boolean('Imprimir Detalle Adicional 2?',
        related='company_id.print_ride_detail2', readonly=False)
    print_ride_detail3 = fields.Boolean('Imprimir Detalle Adicional 3?',
        related='company_id.print_ride_detail3', readonly=False)
    l10n_ec_sri_payment_id = fields.Many2one('l10n_ec.sri.payment.method', string=u'S.R.I Payment Method',
        related='company_id.l10n_ec_sri_payment_id', readonly=False)

    @api.onchange('type_conection_sri', )
    def onchange_type_conection_sri(self):
        if self.type_conection_sri == 'online':
            self.ws_receipt_test = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl"
            self.ws_auth_test = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl"
            self.ws_receipt_production = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantes?wsdl"
            self.ws_auth_production = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantes?wsdl"
        else:
            self.ws_receipt_test = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
            self.ws_auth_test = "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
            self.ws_receipt_production = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl"
            self.ws_auth_production = "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
