# -*- encoding: utf-8 -*-

import os
import time
import logging
import traceback
from lxml import etree
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime

import urllib
from suds import WebFault
from suds.client import Client
from pprint import pformat

from odoo import models, api, fields
from odoo import tools
from odoo.tools.translate import _
import odoo.addons
from odoo.tools.safe_eval import safe_eval as eval
from odoo.exceptions import except_orm, Warning, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
from odoo.tools import float_compare
import base64

from ..models import modules_mapping

_logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {
    'out_invoice': '01',
    'out_refund': '04',
    'debit_note_out': '05',
    'delivery_note': '06',
    'withhold_purchase': '07',
}

DOCUMENT_MODELS = {
    'out_invoice': 'account.move',
    'out_refund': 'account.move',
    'debit_note_out': 'account.move',
    'delivery_note': 'l10n_ec.delivery.note',
    'withhold_purchase': 'l10n_ec.withhold',
}

DOCUMENT_XSD_FILES = {
    'out_invoice': 'Factura_V1.0.0.xsd',
    'out_refund': 'notaCredito_1.1.0.xsd',
    'debit_note_out': 'notaDebito_1.1.1.xsd',
    'delivery_note': 'guiaRemision_1.1.0.xsd',
    'withhold_purchase': 'comprobanteRetencion_1.1.1.xsd',
    'lote_masivo': 'loteMasivo_1.0.0.xsd',
}

DOCUMENT_FIELDS = {
    'out_invoice': 'document_number',
    'out_refund': 'document_number',
    'debit_note_out': 'document_number',
    'delivery_note': 'document_number',
    'withhold_purchase': 'document_number',
}

DOCUMENT_FIELDS_DATE = {
    'out_invoice': 'date_invoice',
    'out_refund': 'date_invoice',
    'debit_note_out': 'date_invoice',
    'delivery_note': 'delivery_date',
    'withhold_purchase': 'creation_date',
}

DOCUMENT_VERSIONS = {
    'out_invoice': '1.1.0',
    'out_refund': '1.1.0',
    'debit_note_out': '1.0.0',
    'delivery_note': '1.1.0',
    'withhold_purchase': '1.0.0',
    'lote_masivo': '1.1.0',
}

XML_HEADERS = {
    'out_invoice': 'factura',
    'out_refund': 'notaCredito',
    'debit_note_out': 'notaDebito',
    'delivery_note': 'guiaRemision',
    'withhold_purchase': 'comprobanteRetencion',
    'lote_masivo': 'lote-masivo',
}

FIELDS_NAME = {
    'out_invoice': 'invoice_out_id',
    'out_refund': 'credit_note_out_id',
    'debit_note_out': 'debit_note_out_id',
    'delivery_note': 'delivery_note_id',
    'withhold_purchase': 'withhold_id',
}

XML_FIELDS_NAME = {
    'simple_xml': 'xml_file',
    'signed_xml': 'xml_signed_file',
    'authorized_xml': 'xml_authorized_file',
}

REPORT_NAME = {
    'out_invoice': 'ecua_documentos_electronicos.e_invoice_qweb',
    'out_refund': 'ecua_documentos_electronicos.e_credit_note_qweb',
    'debit_note_out': 'ecua_documentos_electronicos.e_debit_note_qweb',
    'delivery_note': 'ecua_documentos_electronicos.e_delivery_note_qweb',
    'withhold_purchase': 'ecua_documentos_electronicos.e_retention_qweb',
}

FIELD_FOR_SEND_MAIL_DOCUMENT = {
    'out_invoice': 'send_mail_invoice',
    'out_refund': 'send_mail_credit_note',
    'debit_note_out': 'send_mail_debit_note',
    'delivery_note': 'send_mail_remision',
    'withhold_purchase': 'send_mail_retention',
}


def trunc_decimal(decimal, position):
    decimal = float(decimal)
    before_dec, after_dec = str(decimal).split('.')
    return float('.'.join((before_dec, after_dec[0:position])))


class sri_xml_data(models.Model):

    _name = 'sri.xml.data'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = 'SRI XML Data'
    _rec_name = 'number_document'

    fields_size = {'xml_key': 49,
                   'xml_authorization': 37,
                   }

    _ws_receipt_test = None
    _ws_auth_test = None
    _ws_receipt_production = None
    _ws_auth_production = None
    suds_log_level = logging.INFO
    logging.getLogger('suds.client').setLevel(suds_log_level)
    logging.getLogger('suds.transport').setLevel(suds_log_level)
    logging.getLogger('suds.xsd.schema').setLevel(suds_log_level)
    logging.getLogger('suds.wsdl').setLevel(suds_log_level)

    @api.depends('invoice_out_id', 'credit_note_out_id', 'debit_note_out_id', 'withhold_id', 'delivery_note_id')
    def _compute_document_number(self):
        number = 'SN'
        if self.invoice_out_id:
            number = 'FV: %s' % self.invoice_out_id.display_name
        elif self.credit_note_out_id:
            number = 'NCC: %s' % self.credit_note_out_id.display_name
        elif self.debit_note_out_id:
            number = 'NDC: %s' % self.debit_note_out_id.display_name
        elif self.withhold_id:
            number = 'RET: %s' % self.withhold_id.display_name
        elif self.delivery_note_id:
            number = 'GR: %s' % self.delivery_note_id.display_name
        self.number_document = number

    number_document = fields.Char(u'Document Number', size=256, required=False,
                                  compute='_compute_document_number', store=True, index=True, help=u"",)
    file_xml_path = fields.Char(
        u'Ruta de Archivo XML', size=512, required=False, help=u"",)
    file_signed_path = fields.Char(
        u'Ruta de Archivo Firmado', size=512, required=False, help=u"",)
    file_authorized_path = fields.Char(
        u'Ruta de Archivo Autorizado', size=512, required=False, help=u"",)
    xml_file_version = fields.Char(
        u'Version XML', size=512, required=False, help=u"",)
    xml_key = fields.Char(u'Clave de Acceso', size=49,
                          readonly=True, index=True, help=u"",)
    xml_authorization = fields.Char(
        u'Autorización SRI', size=49, readonly=True, index=True, help=u"",)
    description = fields.Char(u'Description', size=256,
                              readonly=False, help=u"",)
    key_id = fields.Many2one('sri.keys', u'Clave Usada',
                             required=False, index=True, auto_join=True, help=u"",)
    invoice_out_id = fields.Many2one(
        'account.move', u'Factura', required=False, index=True, auto_join=True, help=u"",)
    credit_note_out_id = fields.Many2one(
        'account.move', u'Nota de Crédito', required=False, index=True, auto_join=True, help=u"",)
    debit_note_out_id = fields.Many2one(
        'account.move', u'Nota de Débito', required=False, index=True, auto_join=True, help=u"",)
    withhold_id = fields.Many2one(
        'l10n_ec.withhold', u'Retención', required=False, index=True, auto_join=True, help=u"",)
    delivery_note_id = fields.Many2one(
        'l10n_ec.delivery.note', u'Guia de Remision', required=False, index=True, auto_join=True, help=u"",)
    partner_id = fields.Many2one(
        'res.partner', u'Cliente', required=False, index=True, auto_join=True, help=u"",)
    create_uid = fields.Many2one(
        'res.users', u'Creado por', readonly=True, help=u"",)
    create_date = fields.Datetime(
        u'Fecha de Creación', readonly=True, help=u"",)
    signed_date = fields.Datetime(
        u'Fecha de Firma', readonly=True, index=True, help=u"",)
    send_date = fields.Datetime(u'Fecha de Envío', readonly=True, help=u"",)
    response_date = fields.Datetime(
        u'Fecha de Respuesta', readonly=True, help=u"",)
    authorization_date = fields.Datetime(
        u'Fecha de Autorización', readonly=True, index=True, help=u"",)
    notification_active = fields.Boolean(string=u'Notificación de Documentos Electrónicos no Autorizados?', readonly=False, states={
    }, help=u"Esto permite activar o desactivar las notificaciones del presente documento", default=True)
    xml_type = fields.Selection([('individual', u'Individual'),
                                 ('grouped', u'Agrupado / Lote Masivo'),
                                 ], string=u'Tipo', index=True, readonly=False, default='individual',
                                help=u"",)
    state = fields.Selection([('draft', u'Creado'),
                              # emitido en contingencia no es igual a esperar autorizacion(clave 70)
                              ('contingency', u'Emitido en contingencia'),
                              ('signed', u'Firmado'),
                              # Emitido x Contingencia, en espera de autorizacion
                              ('waiting', u'En Espera de Autorización'),
                              ('authorized', u'Autorizado'),
                              ('returned', u'Devuelta'),
                              ('rejected', u'No Autorizado'),
                              ('cancel', u'Cancelado'),
                              ], string=u'Estado', index=True, readonly=True, default='draft',
                             help=u"",)
    type_environment = fields.Selection([('test', u'Pruebas'),
                                         ('production', u'Producción'),
                                         ], string=u'Tipo de Ambiente', index=True, readonly=True,
                                        help=u"",)
    type_emision = fields.Selection([('normal', u'Normal'),
                                     ('contingency', u'Contingencia'),
                                     ], string=u'Tipo de Emisión', index=True, readonly=True,
                                    help=u"",)
    last_error_id = fields.Many2one(
        'sri.error.code', u'Ultimo Mensaje de error', readonly=True, index=True, auto_join=True, help=u"",)
    send_message_ids = fields.One2many(
        'sri.xml.data.message.line', 'xml_id', u'Mensajes Informativos', required=False, help=u"",)
    try_ids = fields.One2many('sri.xml.data.send.try',
                              'xml_id', u'Send Logs', required=False, help=u"",)
    # campo para enviar los mail a los clientes por lotes, u mejorar el proceso de autorizacion
    send_mail = fields.Boolean(u'Mail enviado?', readonly=False, help=u"",)
    # cuando el documento sea externo,
    # los campos funcionales no se calcularan en ese instante
    # y tampoco se hace el envio al sri en ese instante
    # una tarea cron se encargara de eso
    # este campo es para no calcular los datos cada vez que se ejecute la tarea cron, solo la primera vez
    external_document = fields.Boolean(
        u'Documento Externo?', readonly=True, help=u"",)
    process_now = fields.Boolean(
        u'Procesar Documento Externo?', default=True, readonly=True, help=u"",)
    fields_function_calculate = fields.Boolean(
        u'Campos funcionales calculados?', readonly=False, help=u"",)
    external_data = fields.Text(
        string=u'Informacion Externa importada', readonly=True, help=u"",)
    # campo para el numero de autorizacion cuando se cancelan documentos electronicos
    authorization_to_cancel = fields.Char(
        u'Autorización para cancelar', size=64, readonly=True, help=u"",)
    cancel_date = fields.Datetime(
        u'Fecha de cancelación', readonly=True, help=u"",)
    cancel_user_id = fields.Many2one(
        'res.users', u'Usuario que canceló', readonly=True, help=u"",)

    _sql_constraints = [('invoice_out_id_uniq', 'unique (invoice_out_id)', _('Ya existe una factura electronica con el mismo numero!')),
                        ('credit_note_out_id_uniq', 'unique (credit_note_out_id)', _(
                            'Ya existe una Nota de credito electronica con el mismo numero!')),
                        ('debit_note_out_id_uniq', 'unique (debit_note_out_id)', _(
                            'Ya existe una Nota de debito electronica con el mismo numero!')),
                        ('withhold_id_uniq', 'unique (withhold_id)', _(
                            'Ya existe una Retencion electronica con el mismo numero!')),
                        ('delivery_note_id_uniq', 'unique (delivery_note_id)', _(
                            'Ya existe una Guia de remision electronica con el mismo numero!')),
                        ]

    @api.depends(
        'invoice_out_id',
        'credit_note_out_id',
        'debit_note_out_id',
        'withhold_id',
        'delivery_note_id',
    )
    def _get_company_id(self):
        company_id = self.env.company
        if self.invoice_out_id and self.invoice_out_id.company_id:
            company_id = self.invoice_out_id.company_id.id
        if self.credit_note_out_id and self.credit_note_out_id.company_id:
            company_id = self.credit_note_out_id.company_id.id
        if self.debit_note_out_id and self.debit_note_out_id.company_id:
            company_id = self.debit_note_out_id.company_id.id
        if self.withhold_id and self.withhold_id.company_id:
            company_id = self.withhold_id.company_id.id
        if self.delivery_note_id and self.delivery_note_id.company_id:
            company_id = self.delivery_note_id.company_id.id
        self.company_id = company_id
    company_id = fields.Many2one('res.company', string=u'Compañía',
                                 store=True, compute='_get_company_id', help=u"")

    @api.depends(
        'invoice_out_id',
        'credit_note_out_id',
        'debit_note_out_id',
        'withhold_id',
        'delivery_note_id',
    )
    def _get_ws_type_conection(self):
        printer_model = self.env['l10n_ec.point.of.emission']
        printer_id = False
        if self.invoice_out_id and self.invoice_out_id.printer_id:
            printer_id = self.invoice_out_id.printer_id.id
        if self.credit_note_out_id and self.credit_note_out_id.printer_id:
            printer_id = self.credit_note_out_id.printer_id.id
        if self.debit_note_out_id and self.debit_note_out_id.printer_id:
            printer_id = self.debit_note_out_id.printer_id.id
        if self.withhold_id and self.withhold_id.printer_id:
            printer_id = self.withhold_id.printer_id.id
        if self.delivery_note_id and self.delivery_note_id.printer_id:
            printer_id = self.delivery_note_id.printer_id.id
        if printer_id:
            printer = printer_model.browse(printer_id)
            if printer.ws_type_conection:
                self.ws_type_conection = printer.ws_type_conection
            elif printer.agency_id and printer.agency_id.ws_type_conection:
                self.ws_type_conection = printer.agency_id.ws_type_conection
            elif self.env.user.company_id.ws_type_conection:
                self.ws_type_conection = self.env.user.company_id.ws_type_conection
        elif self.env.user.company_id.ws_type_conection:
            self.ws_type_conection = self.env.user.company_id.ws_type_conection

    ws_type_conection = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string=u'Tipo de Conexión',
        store=True, compute="_get_ws_type_conection")

    @api.depends(
        'invoice_out_id',
        'credit_note_out_id',
        'debit_note_out_id',
        'withhold_id',
        'delivery_note_id',
    )
    def _get_printer_id(self):
        printer_id = False
        if self.invoice_out_id and self.invoice_out_id.printer_id:
            printer_id = self.invoice_out_id.printer_id.id
        if self.credit_note_out_id and self.credit_note_out_id.printer_id:
            printer_id = self.credit_note_out_id.printer_id.id
        if self.debit_note_out_id and self.debit_note_out_id.printer_id:
            printer_id = self.debit_note_out_id.printer_id.id
        if self.withhold_id and self.withhold_id.printer_id:
            printer_id = self.withhold_id.printer_id.id
        if self.delivery_note_id and self.delivery_note_id.printer_id:
            printer_id = self.delivery_note_id.printer_id.id
        self.printer_id = printer_id
    printer_id = fields.Many2one('l10n_ec.point.of.emission', string=u'Punto de Emisión',
                                 store=True, compute='_get_printer_id', help=u"")
    shop_id = fields.Many2one(
        'l10n_ec.agency', string=u'Agencia', related="printer_id.agency_id", store=True)

    @api.model
    def get_current_wsClient(self, conection_type):
        # Debido a que el servidor me esta rechazando las conexiones contantemente, es necesario que se cree una sola instancia
        # Para conexion y asi evitar un reinicio constante de la comunicacion
        wsClient = None
        company = self.env.user.company_id
        try:
            if conection_type == 'ws_receipt_test':
                receipt_test = company.ws_receipt_test
                if self.ws_type_conection == 'offline':
                    receipt_test = company.ws_receipt_test_offline
                if self._ws_receipt_test and self._ws_receipt_test.wsdl.url == receipt_test:
                    wsClient = self._ws_receipt_test
                else:
                    wsClient = Client(receipt_test, timeout=company.ws_timeout)
                    self._ws_receipt_test = wsClient
            if conection_type == 'ws_auth_test':
                ws_auth_test = company.ws_auth_test
                if self.ws_type_conection == 'offline':
                    ws_auth_test = company.ws_auth_test_offline
                if self._ws_auth_test and self._ws_auth_test.wsdl.url == ws_auth_test:
                    wsClient = self._ws_auth_test
                else:
                    wsClient = Client(ws_auth_test, timeout=company.ws_timeout)
                    self._ws_auth_test = wsClient
            if conection_type == 'ws_receipt_production':
                ws_receipt_production = company.ws_receipt_production
                if self.ws_type_conection == 'offline':
                    ws_receipt_production = company.ws_receipt_production_offline
                if self._ws_receipt_production and self._ws_receipt_production.wsdl.url == ws_receipt_production:
                    wsClient = self._ws_receipt_production
                else:
                    wsClient = Client(ws_receipt_production,
                                      timeout=company.ws_timeout)
                    self._ws_receipt_production = wsClient
            if conection_type == 'ws_auth_production':
                ws_auth_production = company.ws_auth_production
                if self.ws_type_conection == 'offline':
                    ws_auth_production = company.ws_auth_production_offline
                if self._ws_auth_production and self._ws_auth_production.wsdl.url == ws_auth_production:
                    wsClient = self._ws_auth_production
                else:
                    wsClient = Client(ws_auth_production,
                                      timeout=company.ws_timeout)
                    self._ws_auth_production = wsClient
        except Exception as e:
            error = self._clean_str(tools.ustr(e))
            _logger.warning(
                u"Error in Conection with web services of SRI, set in contingency mode. Error: %s", error)
        return wsClient

    @api.model
    def get_sequence(self, printer_id, number):
        res = None
        try:
            number_splited = number.split('-')
            res = int(number_splited[2])
        except:
            res = None
        return res

    @api.model
    def _clean_str(self, string_to_reeplace, list_characters=None, separator=''):
        """
        Reemplaza caracteres por otros caracteres especificados en la lista
        @param string_to_reeplace:  string a la cual reemplazar caracteres
        @param list_characters:  Lista de tuplas con dos elementos(elemento uno el caracter a reemplazar, elemento dos caracter que reemplazara al elemento uno)
        @return: string con los caracteres reemplazados
        """
        if not string_to_reeplace:
            return string_to_reeplace
        caracters = ['.', ',', '-', '\a', '\b', '\f', '\n', '\r', '\t', '\v']
        for c in caracters:
            string_to_reeplace = string_to_reeplace.replace(c, separator)
        if not list_characters:
            list_characters = [(u'á', 'a'), (u'à', 'a'), (u'ä', 'a'), (u'â', 'a'), (u'Á', 'A'), (u'À', 'A'), (u'Ä', 'A'), (u'Â', 'A'),
                               (u'é', 'e'), (u'è', 'e'), (u'ë', 'e'), (u'ê',
                                                                       'e'), (u'É', 'E'), (u'È', 'E'), (u'Ë', 'E'), (u'Ê', 'E'),
                               (u'í', 'i'), (u'ì', 'i'), (u'ï', 'i'), (u'î',
                                                                       'i'), (u'Í', 'I'), (u'Ì', 'I'), (u'Ï', 'I'), (u'Î', 'I'),
                               (u'ó', 'o'), (u'ò', 'o'), (u'ö', 'o'), (u'ô',
                                                                       'o'), (u'Ó', 'O'), (u'Ò', 'O'), (u'Ö', 'O'), (u'Ô', 'O'),
                               (u'ú', 'u'), (u'ù', 'u'), (u'ü', 'u'), (u'û',
                                                                       'u'), (u'Ú', 'U'), (u'Ù', 'U'), (u'Ü', 'U'), (u'Û', 'U'),
                               (u'ñ', 'n'), (u'Ñ', 'N'), (u'/', '-'), (u'&', 'Y'), (u'º', ''), (u'´', '')]
        for character in list_characters:
            string_to_reeplace = string_to_reeplace.replace(
                character[0], character[1])
        SPACE = ' '
        codigo_ascii = False
        # en range el ultimo numero no es inclusivo asi que agregarle uno mas
        # espacio en blanco
        range_ascii = [32]
        # numeros
        range_ascii += range(48, 57 + 1)
        # letras mayusculas
        range_ascii += range(65, 90 + 1)
        # letras minusculas
        range_ascii += range(97, 122 + 1)
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
        return ''.join(string_to_reeplace.splitlines())

    @api.model
    def _get_environment(self, company):
        # Si no esta configurado el campo, x defecto tomar pruebas
        res = '1'
        if company.type_environment == 'production':
            res = '2'
        return res

    @api.model
    def check_emision(self, environment):
        """Este metodo debera verificar la conexion con el ws del SRI
        :param environment: Puede ser los siguientes ambientes :
            1 : Emision normal
            2 : emision en Contingencia
        :rtype: Devuelve el tipo de emision que esta disponible en este momento
        """
        company = self.env.user.company_id
        if not company.ws_receipt_test:
            raise Warning(
                _(u"Debe configurar la direccion del webservice de pruebas del SRI"))
        if not company.ws_receipt_production:
            raise Warning(
                _(u"Debe configurar la direccion del webservice de produccion del SRI"))
        # Durante pruebas solo enviar 1
        res = '1'
        # CHECKME: se debe asumir que hay conexion en la creacion de los datos
        if 'sign_now' in self.env.context and not self.env.context.get('sign_now', False):
            return res
        if environment == '1':
            try:
                code = urllib.request.urlopen(company.ws_receipt_test).getcode()
                _logger.info(u"Conection Succesful with %s. Code %s",
                             company.ws_receipt_test, code)
                if code == 200:
                    res = '1'
                else:
                    res = '2'
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(
                    u"Error in Conection with %s, set in contingency mode. ERROR: %s", company.ws_receipt_test, error)
                # no pasar que es contingencia
                res = '1'
        elif environment == '2':
            try:
                code = urllib.request.urlopen(
                    company.ws_receipt_production).getcode()
                _logger.info(u"Conection Succesful with %s. Code %s",
                             company.ws_receipt_production, code)
                if code == 200:
                    res = '1'
                else:
                    res = '2'
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(u"Error in Conection with %s, set in contingency mode. ERROR: %s",
                                company.ws_receipt_production, error)
                # no pasar que es contingencia
                res = '1'
        return res

    @api.model
    def _is_document_authorized(self, invoice_type):
        company = self.env.user.company_id
        document_active = False
        if invoice_type == 'out_invoice' and company.electronic_invoice:
            document_active = True
        elif invoice_type == 'out_refund' and company.electronic_credit_note:
            document_active = True
        elif invoice_type == 'debit_note_out' and company.electronic_debit_note:
            document_active = True
        elif invoice_type == 'delivery_note' and company.electronic_delivery_note:
            document_active = True
        elif invoice_type == 'withhold_purchase' and company.electronic_withhold:
            document_active = True
        elif invoice_type == 'lote_masivo' and company.electronic_batch:
            document_active = True
        return document_active

    @api.model
    def is_enviroment_production(self, invoice_type):
        """
        Verifica si esta en ambiente de produccion y el tipo de documento esta habilitado para facturacion electronica
        @param invoice_type: Puede ser los tipos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
            lote_masivo : Lote Masivo
        @requires: bool True si el documento esta habilidado para facturacion electronica y en modo produccion
            False caso contrario
        """
        company = self.env.user.company_id
        res = False
        enviroment = self._get_environment(company)
        # verificar si el tipo de documento esta configurado como autorizado para emitir
        # antes de verificar si el webservice responde,
        # para no hacer peticion al webservice en vano, si el documento no esta autorizado a emitir
        if enviroment == '2' and self._is_document_authorized(invoice_type):
            res = True
        return res

    @api.model
    def get_xml_string(self, xml_data_id, field_name='file_signed'):
        """Devuelve la informacion de los archivos xml binarios en la clase lxml.etree para su manipulacion
        :param xml_data_id: ID xml_data registro
        :param field_name: Puede ser los campos :
            xml_file : Archivo Generado Sin Firmar
            xml_signed_file : Archivo Generado Firmado
            xml_authorized_file : Archivo Autorizado
        :rtype: objeto tipo lxml.etree o False en caso de que el campo este vacio
        """
        util_model = self.env['ecua.utils']
        # TODO: convertir al formato adecuado
        res = etree.XML(self.get_file(xml_data_id, field_name))
        util_model.indent(res)
        res = tostring(res, encoding="UTF-8")
        return res

    @api.model
    def generate_info_tributaria(self, xml_id, node, document_type, environment, emission, company, printer_id, sequence, date_document):
        """Asigna al nodo raiz la informacion tributaria que es comun en todos los documentos, asigna clave interna
        al documento para ser firmado posteriormente
        :param xml_id: identification xml_data
        :param node: tipo Element
        :param document_type: Puede ser los tipos :
            01 : Factura
            04 : Nota de Credito
            05 : Nota de Debito
            06 : Guia de Remision
            07 : Comprobante de Retencion
        :param environment: Puede ser los siguientes ambientes :
            1 : Pruebas
            2 : Produccion
        :param emission: El tipo de emision puede ser:
            1 : Emision Normal
            2 : Emision por Indisponibilidad del Sistema
        :param company: compania emisora
        :param printer_id: Punto de Emision
        :param sequence: Numero de Documento
        :rtype: objeto root agregado con info tributaria

        """
        key_model = self.env['sri.keys']
        printer_model = self.env['l10n_ec.point.of.emission']
        printer = printer_model.browse(printer_id)
        infoTributaria = SubElement(node, "infoTributaria")
        SubElement(infoTributaria, "ambiente").text = environment
        # emision para 1 pruebas, 2 produccion, 3 contingencia
        # pero webservice solo acepta 1 emision normal, 2 emision por contingencia
        SubElement(infoTributaria, "tipoEmision").text = emission
        xml_data = self.browse(xml_id)
        razonSocial = 'PRUEBAS SERVICIO DE RENTAS INTERNAS'
        if environment == '2':
            razonSocial = self._clean_str(company.partner_id.name)
        SubElement(infoTributaria, "razonSocial").text = razonSocial
        # Debe existir un nombre comercial en la definicion del partner
        SubElement(infoTributaria, "nombreComercial").text = razonSocial
        SubElement(infoTributaria, "ruc").text = company.partner_id.ref
        # si no hay clave, generar la siguiente
        if not xml_data.key_id:
            key_id = key_model.get_next_key(environment, emission)
        # si ya tengo clave, tomar esa
        # TODO: si fue emitida por contigencia, se debe cambiar la clave??
        else:
            key_id = xml_data.key_id.id
        clave_acceso = xml_data.xml_key
        if not clave_acceso:
            clave_acceso = key_model.get_single_key(
                key_id, document_type, environment, printer_id, sequence, emission, xml_data.xml_type, date_document)
        SubElement(infoTributaria, "claveAcceso").text = clave_acceso
        SubElement(infoTributaria, "codDoc").text = document_type
        SubElement(infoTributaria, "estab").text = printer.shop_id.number
        SubElement(infoTributaria, "ptoEmi").text = printer.number
        SubElement(infoTributaria, "secuencial").text = key_model.fill_padding(
            sequence, 9)
        # Debe ser la direccion matriz
        company_address = company.partner_id and company.partner_id.street or printer.shop_id.address_id.street
        SubElement(infoTributaria, "dirMatriz").text = self._clean_str(
            company_address or '')
        return key_id, clave_acceso, node

    @api.model
    def check_xsd(self, xml_string, xsd_file_name='factura_1.1.1.xsd'):
        try:
            xsd_file = tools.file_open(os.path.join(
                'ecua_documentos_electronicos', 'data', 'xsd', xsd_file_name))
            schema_root = etree.XML(xsd_file.read())
            schema = etree.XMLSchema(schema_root)
            parser = etree.XMLParser(schema=schema)
            root = etree.fromstring(xml_string, parser)
        except Exception as e:
            #error = self._clean_str(tools.ustr(e))
            #logger.notifyChannel(u"Error verifing xsd schema %s" % (xsd_file_name), netsvc.LOG_WARNING, error)
            # print traceback.format_exc()
            return False
        return True

    @api.model
    def _generate_partner_login(self, xml_id, document_id, invoice_type):
        """Crea el login del cliente en caso de ser la primera vez
        :param xml_id: identificador xml_data
        :param document_id: identificador del documento
        :param invoice_type: Puede ser los tipos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
            lote_masivo : Lote Masivo
        :rtype: user, password generadas
        """
        user, password = "", ""
        document_type = modules_mapping.get_document_type(invoice_type)
        model_name = modules_mapping.get_model_name(document_type)
        if model_name:
            res_model = self.env[model_name].browse(document_id)
            # asumo que todos los modelos tienen el cliente con el mismo nombre de campo
            # en caso de no ser asi, utilizar FIELDS_MAPPING
            partner = res_model.partner_id
            if partner and (not partner.electronic_user or not partner.electronic_password):
                # TODO: como generar la contraseña???
                user = partner.ref
                password = partner.ref
                partner.write({'electronic_user': user,
                               'electronic_password': password,
                               })
            elif partner:
                user = partner.electronic_user
                password = partner.electronic_password
        return user, password

    @api.model
    def generate_xml_file(self, xml_id, document_id, invoice_type, type_grouped='individual'):
        """Genera estructura xml del archivo a ser firmado
        :param xml_id: identificador xml_data
        :param document_id: identificador del documento a firmar
        :param invoice_type: Puede ser los tipos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
            lote_masivo : Lote Masivo
        :param type_grouped: El tipo de agrupado puede ser:
            individual : Individual
            grouped : Lotes Masivos
        :rtype: objeto root agregado con info tributaria
        """
        # Cuando se encuentre en un ambiente de pruebas el sistema se debera usar para la razon social
        # PRUEBAS SERVICIO DE RENTAS INTERNAS
        partner_mail_model = self.env['res.partner.mail']
        util_model = self.env['ecua.utils']
        key_model = self.env['sri.keys']
        company = self.env.user.company_id
        sign_now = self.env.context.get('sign_now', True)
        xml_data = self.browse(xml_id)
        document_type = modules_mapping.get_document_type(invoice_type)
        field_name = modules_mapping.get_field_name(document_type)
        model_name = modules_mapping.get_model_name(document_type)
        doc_model = self.env[model_name]
        environment = self._get_environment(company)
        # cuando fallo el envio o la autorizacion, puedo pasar el modo de emision
        # para continuar el proceso segun ese modo de emision
        # si no tengo emision, verificar el webservice para saber el modo de emision
        emission = self.env.context.get('emission', "1")
        if not emission and xml_data.external_document:
            emission = self.check_emision(environment)
        # Para los documentos externos siempre debe ser en emision normal por el desfase
        if xml_data.external_document:
            emission = "1"
        document = doc_model.browse(document_id)
        partner_id = document.partner_id
        send_mail_for_document = FIELD_FOR_SEND_MAIL_DOCUMENT[invoice_type] and getattr(
            company, FIELD_FOR_SEND_MAIL_DOCUMENT[invoice_type], False) or False
        printer_id = document.printer_id.id
        sequence = ''
        if xml_data.xml_type == 'individual':
            sequence = self.get_sequence(printer_id, document[field_name])
        root = Element(XML_HEADERS.get(invoice_type), id="comprobante",
                       version=DOCUMENT_VERSIONS.get(invoice_type))
        key_id, clave_acceso, root = self.generate_info_tributaria(xml_id, root, DOCUMENT_TYPES.get(invoice_type),
                                                                   environment, emission, company, printer_id, sequence,
                                                                   document[DOCUMENT_FIELDS_DATE.get(invoice_type)])
        if key_id:
            key_model.write([key_id], {'state': 'used'})
        else:
            if environment == '1' and emission == '1':
                _logger.warning(
                    u"Can't find key to generate xml file. No es posible encontrar claves de tipo pruebas para la generacion del archivo xml")
            elif environment == '2' and emission == '1':
                _logger.warning(
                    u"Can't find key to generate xml file. No es posible encontrar claves de tipo producción para la generacion del archivo xml")
            # Si no tengo claves de contingencia no debo permitir seguir en el proceso, ya que despues no puedo generar el xml correctamente
            elif emission == '2':
                _logger.warning(
                    u"Can't find key to generate xml file. No es posible encontrar claves de tipo contingencia para la generacion del archivo xml, no se puede continuar con la operación actual")
                #raise osv.except_osv(_(u'Error!!!'), _(u'No es posible encontrar claves de tipo contingencia para la generacion del archivo xml, no se puede continuar con la operación actual'))
        state = xml_data.state
        type_environment = ''
        if environment == '1':
            type_environment = 'test'
        elif environment == '2':
            type_environment = 'production'
        type_emision = ''
        if xml_data.external_document:
            type_emision = 'normal'
        else:
            if emission == '1':
                type_emision = 'normal'
            else:
                type_emision = 'contingency'
                # pasar el estado de contingencia para que la tarea cron se encargue de procesarla
                state = 'contingency'
        xml_data.write({'type_environment': type_environment,
                        'type_emision': type_emision,
                        'key_id': key_id,
                        'state': state,
                        'xml_key': clave_acceso,
                        'partner_id': partner_id and partner_id.id or False,
                        })
        # escribir en los objetos relacionados, la clave de acceso y el xml_data para pasar la relacion
        if xml_data.invoice_out_id:
            xml_data.invoice_out_id.write({'xml_key': clave_acceso,
                                           'xml_data_id': xml_id,
                                           })
        elif xml_data.credit_note_out_id:
            xml_data.credit_note_out_id.write({'xml_key': clave_acceso,
                                               'xml_data_id': xml_id,
                                               })
        elif xml_data.debit_note_out_id:
            xml_data.debit_note_out_id.write({'xml_key': clave_acceso,
                                              'xml_data_id': xml_id,
                                              })
        elif xml_data.withhold_id:
            xml_data.withhold_id.write({'xml_key': clave_acceso,
                                        'xml_data_id': xml_id,
                                        })
        elif xml_data.delivery_note_id:
            xml_data.delivery_note_id.write({'xml_key': clave_acceso,
                                             'xml_data_id': xml_id,
                                             })
        # si estoy con un documento externo, y no debo hacer el proceso electronico en ese momento
        # no tomar la info de los documentos, la tarea cron debe encargarse de eso
        if sign_now:
            if invoice_type == 'out_invoice':
                doc_model.get_info_factura(document_id, root)
            # nota de credito
            elif invoice_type == 'out_refund':
                doc_model.get_info_credit_note(document_id, root)
            # nota de debito
            elif invoice_type == 'debit_note_out':
                doc_model.get_info_debit_note(document_id, root)
            elif invoice_type == 'withhold_purchase':
                doc_model.get_info_withhold(document_id, root)
            elif invoice_type == 'delivery_note':
                doc_model.get_info_delivery_note(document_id, root)
        # Se identa con propositos de revision, no debe ser asi al enviar el documento
        util_model.indent(root)
        string_data = tostring(root, encoding="UTF-8")
        self.check_xsd(string_data, DOCUMENT_XSD_FILES.get(invoice_type))
        binary_data = base64.encodestring(string_data)
        # enviar a crear los datos del cliente en caso de no estar configurados
        self._generate_partner_login(xml_id, document_id, invoice_type)
        return string_data, binary_data

    @api.model
    def get_xml_file(self, document_id, model, file_type):
        """En base al id del documento se obtiene el campo xml que se necesite
        :paran document_id: id del objeto a buscar
        :param model: Puede ser los siguientes modelos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
        :param file_type: este debe ser
            simple_xml: estructura del xml sin firmar
            signed_xml: estructura del xml firmado
            authorized_xml: estructura del xml firmado y autorizado
        :rtype: binary file data
        """
        res = None
        xml_recs = self.search([(FIELDS_NAME.get(model), '=', document_id)])
        if xml_recs:
            xml = xml_recs[0]
            if xml.__hasattr__(XML_FIELDS_NAME.get(file_type)):
                res = xml[XML_FIELDS_NAME.get(file_type)]
        return res

    @api.model
    def get_xml_authorization(self, document_id, model):
        """En base al id del documento se obtiene el campo xml que se necesite
        :paran document_id: id del objeto a buscar
        :param model: Puede ser los siguientes modelos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
        :rtype: binary file data
        """
        res = None
        xml_recs = self.search([(FIELDS_NAME.get(model), '=', document_id)])
        if xml_recs:
            xml = xml_recs[0]
            res = xml.xml_authorization
        return res

    @api.model
    def get_xml_data_id(self, document_id, invoice_type):
        """En base al id del documento se obtiene el id del registro con la informacion electronica
        :paran document_id: id del objeto a buscar
        :param invoice_type: Puede ser los siguientes modelos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
        :rtype: int, id del modelo sri.xml.data
        """
        return self.search([(FIELDS_NAME.get(invoice_type), '=', document_id)])

    @api.model
    def _create_messaje_response(self, xml_id, messajes, authorized, raise_error):
        message_model = self.env['sri.xml.data.message.line']
        error_model = self.env['sri.error.code']
        last_error_rec = self.env['sri.error.code'].browse()
        xml_rec = self.browse(xml_id)
        last_error_id, raise_error = False, False
        vals_messages = {}
        method_messages = 'create'
        messages_recs = message_model.browse()
        messages_error = []
        for message in messajes:
            method_messages = 'create'
            messages_recs = message_model.browse()
            # si no fue autorizado, y es clave 70, escribir estado para que la tarea cron se encargue de autorizarlo
            # el identificador puede ser str o numerico
            if not authorized and message.get('identificador') and message.get('identificador') in ('70', 70):
                _logger.warning(u"Clave 70, en espera de autorizacion. %s %s", message.get(
                    'mensaje', ''), message.get('informacionAdicional', ''))
                xml_rec.write({'state': 'waiting'})
                raise_error = False
            error_recs = error_model.search(
                [('code', '=', message.get('identificador'))])
            if error_recs:
                last_error_rec = error_recs[0]
            # el mensaje 60 no agregarlo, es informativo y no debe lanzar excepcion por ese error
            if message.get('identificador') and message.get('identificador') not in ('60', 60):
                messages_error.append("%s. %s" % (message.get(
                    'mensaje'), message.get('informacionAdicional')))
            vals_messages = {'xml_id': xml_id,
                             'message_code_id': last_error_rec.id,
                             'message_type': message.get('tipo'),
                             'other_info': message.get('informacionAdicional'),
                             'message': message.get('mensaje'),
                             }
            for msj in xml_rec.send_message_ids:
                # si ya existe un mensaje con el mismo codigo
                # y el texto es el mismo, modificar ese registro
                if msj.message_type in ('ERROR', 'ERROR DE SERVIDOR') and last_error_rec:
                    last_error_id = last_error_rec.id
                if msj.message_code_id and last_error_rec:
                    if msj.message_code_id.id == last_error_rec.id and (msj.message == message.get('mensaje') or msj.other_info == message.get('other_info')):
                        method_messages = 'write'
                        messages_recs += msj
            if method_messages == 'write' and messages_recs:
                messages_recs.write(vals_messages)
            elif method_messages == 'create':
                message_model.create(vals_messages)
                if vals_messages.get('message_type', '') in ('ERROR', 'ERROR DE SERVIDOR') and last_error_rec:
                    last_error_id = last_error_rec.id
        # una vez creado todos los mensajes, si hubo uno de error escribirlo como el ultimo error recibido
        if last_error_id:
            xml_rec.write({'last_error_id': last_error_id})
        return messages_error, raise_error

    def _free_key_in_use(self):
        # cambiar clave de acceso solo cuando la clave sea tipo contingencia
        # si es documento externo, no cambiar clave por ninguna razon
        if self.key_id and self.key_id.key_type == 'contingency' and not self.external_document:
            self.key_id.write({'state': 'draft'})
            self.write({'key_id': False, 'xml_key': ''})
        return True

    @api.model
    def _send_xml_data_to_valid(self, xml_id, xml_field, client_ws, client_ws_auth):
        """
        Enviar a validar el comprobante con la clave de acceso
        :paran xml_id: Objeto a escribir
        :param xml_field: este debe ser
            xml_signed_file : Archivo Firmado
        :param client_ws: direccion del webservice para realizar el proceso
        """
        xml_rec = self.browse(xml_id)
        try_model = self.env['sri.xml.data.send.try']
        xml_rec.write({'send_date': time.strftime(DTF)})
        company = self.env.user.company_id
        response = False
        try:
            if tools.config.get('no_electronic_documents') and company.type_environment == 'production':
                raise Exception(
                    _('NO SE ENVIA A AUTORIAZAR EN MODO DESARROLLO'))
            send = True
            # En caso de ya haber tratado de enviar anteriormente, no debe enviar 2 veces
            if len(xml_rec.try_ids) >= 1:
                # En caso de ya haber hecho un intento es necesario que se verifique directamente con la clave de acceso
                try_rec = try_model.create({'xml_id': xml_id,
                                            'send_date': time.strftime(DTF),
                                            'type_send': 'check',
                                            })
                responseAuth = client_ws_auth.service.autorizacionComprobante(
                    claveAccesoComprobante=xml_rec.xml_key)
                try_rec.write({'response_date': time.strftime(DTF)})
                ok, msgs = self._process_response_autorization(
                    xml_id, responseAuth)
                if ok:
                    response = {
                        'estado': 'RECIBIDA',
                    }
                    # Si ya fue recibida y autorizada, no tengo que volver a enviarla
                    send = False
            if self.env.context.get('no_send'):
                send = False
            if send:
                try_rec = try_model.create({'xml_id': xml_id,
                                            'send_date': time.strftime(DTF),
                                            'type_send': 'send',
                                            })
                xml_string = base64.encodestring(
                    self.get_file(xml_id, xml_field)).decode()
                response = client_ws.service.validarComprobante(xml=xml_string)
                try_model.write({'response_date': time.strftime(DTF)})
                _logger.info(u"Send file succesful, claveAcceso %s. %s", xml_rec.xml_key, str(
                    response.estado) if hasattr(response, 'estado') else u'SIN RESPUESTA')
            xml_rec.write({'response_date': time.strftime(DTF)})
        except WebFault as ex:
            error = self._clean_str(tools.ustr(ex))
            xml_rec.write({'state': 'waiting'})
            ok = False
            _logger.info(u"Error de servidor. %s", error)
            messajes = [{'identificador': '50',
                         'informacionAdicional': u'Cuando ocurre un error inesperado en el servidor.',
                         'mensaje': u'Error Interno General del servidor',
                         'tipo': 'ERROR DE SERVIDOR',
                         }
                        ]
            self._create_messaje_response(xml_id, messajes, ok, False)
        except Exception as e:
            error = self._clean_str(tools.ustr(e))
            _logger.info(u"can\'t validate document in %s, claveAcceso %s. ERROR: %s", str(
                client_ws), xml_rec.xml_key, error)
            tr = self._clean_str(tools.ustr(traceback.format_exc()))
            _logger.info(u"can\'t validate document in %s, claveAcceso %s. TRACEBACK: %s", str(
                client_ws), xml_rec.xml_key, tr)
            response = False
            xml_rec.write({'state': 'waiting'})
            ok = False
        return response

    @api.model
    def _process_response_check(self, xml_id, response):
        """
        Procesa la respuesta del webservice
        si fue devuelta, devolver False los mensajes 
        si fue recibida, devolver True y los mensajes
        """
        xml_rec = self.browse(xml_id)
        ok, error, previous_authorized = False, False, False
        msj_res = []
        if response and not isinstance(response, dict):
            if hasattr(response, 'estado') and response.estado == 'DEVUELTA':
                # si fue devuelta, intentar nuevamente, mientras no supere el numero maximo de intentos
                xml_rec.write({'state': 'returned'})
                ok = False
            else:
                ok = True
            try:
                comprobantes = hasattr(
                    response.comprobantes, 'comprobante') and response.comprobantes.comprobante or []
                for comprobante in comprobantes:
                    for msj in comprobante.mensajes.mensaje:
                        msj_res.append({'identificador': msj.identificador if hasattr(msj, 'identificador') else u'',
                                        'informacionAdicional': msj.informacionAdicional if hasattr(msj, 'informacionAdicional') else u'',
                                        'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else u'',
                                        'tipo': msj.tipo if hasattr(msj, 'tipo') else u'',
                                        })
                        # si el mensaje es error, se debe mostrar el msj al usuario
                        if hasattr(msj, 'tipo') and msj.tipo == 'ERROR':
                            error = True
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.info(
                    u"can\'t validate document, claveAcceso %s. ERROR: %s", xml_rec.xml_key, error)
                tr = self._clean_str(tools.ustr(traceback.format_exc()))
                _logger.info(
                    u"can\'t validate document, claveAcceso %s. TRACEBACK: %s", xml_rec.xml_key, tr)
                ok = False
        if response and isinstance(response, dict) and response.get('estado', False) == 'RECIBIDA':
            ok = True
            previous_authorized = True
        return ok, msj_res, error, previous_authorized

    @api.model
    def _send_xml_data_to_autorice(self, xml_id, xml_field, client_ws):
        """
        Envia a autorizar el archivo
        :paran xml_id: Objeto a escribir
        :param xml_field: este debe ser
            xml_signed_file : Archivo Firmado
        :param client_ws: direccion del webservice para realizar el proceso
        """
        xml_rec = self.browse(xml_id)
        try:
            response = client_ws.service.autorizacionComprobante(
                claveAccesoComprobante=xml_rec.xml_key)
        except WebFault as ex:
            response = False
            xml_rec.write({'state': 'waiting'})
            error = self._clean_str(tools.ustr(ex))
            _logger.info(u"Error de servidor: %s", error)
            messajes = [{'identificador': '50',
                         'informacionAdicional': u'Cuando ocurre un error inesperado en el servidor.',
                         'mensaje': u'Error Interno General del servidor',
                         'tipo': 'ERROR DE SERVIDOR',
                         }
                        ]
            self._create_messaje_response(xml_id, messajes, False, False)
        except Exception as e:
            response = False
            xml_rec.write({'state': 'waiting'})
            # FIX: pasar a unicode para evitar problemas
            error = self._clean_str(tools.ustr(e))
            _logger.warning(
                u"Error send xml to server %s. ERROR: %s", client_ws, error)
        return response

    @api.model
    def _process_response_autorization(self, xml_id, response):
        """
        Procesa la respuesta del webservice
        si fue devuelta, devolver False los mensajes 
        si fue recibida, devolver True y los mensajes
        """
        xml_rec = self.browse(xml_id)
        vals = {}
        ok = False
        msj_res = []
        no_write = self.env.context.get('no_write', False)

        def dump(obj):
            data_srt = pformat(obj, indent=3, depth=5)
            _logger.warning(u"Data dump: %s", data_srt)
        if not response:
            # si no tengo respuesta, dejar el documento en espera de autorizacion, para que la tarea cron se encargue de procesarlo y no quede firmado el documento
            _logger.warning(
                u"Authorization response error, No response get. Documento en espera de autorizacion")
            xml_rec.write({'state': 'waiting'})
            return ok, msj_res
        if isinstance(response, object) and not hasattr(response, 'autorizaciones'):
            # si no tengo respuesta, dejar el documento en espera de autorizacion, para que la tarea cron se encargue de procesarlo y no quede firmado el documento
            _logger.warning(
                u"Authorization response error, No Autorizacion in response. Documento en espera de autorizacion")
            xml_rec.write({'state': 'waiting'})
            return ok, msj_res
        # a veces el SRI devulve varias autorizaciones, unas como no autorizadas
        # pero otra si autorizada, si pasa eso, tomar la que fue autorizada
        # las demas ignorarlas
        autorizacion_list = []
        list_aux = []
        authorization_date = False
        if isinstance(response.autorizaciones, (str)):
            _logger.warning(u"Authorization data error, reponse message is not correct. %s", str(
                response.autorizaciones))
            dump(response)
            return ok, msj_res
        if not isinstance(response.autorizaciones.autorizacion, list):
            list_aux = [response.autorizaciones.autorizacion]
        else:
            list_aux = response.autorizaciones.autorizacion
        for doc in list_aux:
            estado = doc.estado
            if estado == 'AUTORIZADO':
                autorizacion_list.append(doc)
                break
        # si ninguna fue autorizada, procesarlas todas, para que se creen los mensajes
        if not autorizacion_list:
            autorizacion_list = list_aux
        for doc in autorizacion_list:
            estado = doc.estado
            if estado == 'AUTORIZADO' and not no_write:
                ok = True
                # TODO: escribir la autorizacion en el archivo xml o no???
                numeroAutorizacion = doc.numeroAutorizacion
                _logger.info(u"Authorization succesful, claveAcceso %s. Autohrization: %s",
                             xml_rec.xml_key, str(numeroAutorizacion))
                # tomar la fecha de autorizacion que envia el SRI
                authorization_date = doc.fechaAutorizacion if hasattr(
                    doc, 'fechaAutorizacion') else False
                # si no es una fecha valida, tomar la fecha actual del sistema
                if not isinstance(authorization_date, datetime):
                    authorization_date = time.strftime(DTF)
                vals['xml_authorization'] = str(numeroAutorizacion)
                vals['authorization_date'] = authorization_date.strftime(DTF)
                vals['state'] = 'authorized'
                # escribir en los objetos relacionados, la autorizacion y fecha de autorizacion
                if xml_rec.invoice_out_id:
                    xml_rec.invoice_out_id.write({'electronic_authorization_sri': str(numeroAutorizacion),
                                                  'authorization_date': authorization_date.strftime(DTF),
                                                  })
                elif xml_rec.credit_note_out_id:
                    xml_rec.credit_note_out_id.write({'electronic_authorization_sri': str(numeroAutorizacion),
                                                      'authorization_date': authorization_date.strftime(DTF),
                                                      })
                elif xml_rec.debit_note_out_id:
                    xml_rec.debit_note_out_id.write({'electronic_authorization_sri': str(numeroAutorizacion),
                                                     'authorization_date': authorization_date.strftime(DTF),
                                                     })
                elif xml_rec.withhold_id:
                    xml_rec.withhold_id.write({'electronic_authorization_sri': str(numeroAutorizacion),
                                               'authorization_date': authorization_date.strftime(DTF),
                                               })
                elif xml_rec.delivery_note_id:
                    xml_rec.delivery_note_id.write({'electronic_authorization_sri': str(numeroAutorizacion),
                                                    'authorization_date': authorization_date.strftime(DTF),
                                                    })
                # crear el xml con los datos de autorizacion
            else:
                # si no fue autorizado, validar que no sea clave 70
                ok = False
                if not self.env.context.get('no_change_state', False):
                    vals['state'] = 'rejected'
            if vals and not no_write:
                xml_rec.write(vals)
                # si fue autorizado, enviar a crear el xml
                if 'state' in vals and vals['state'] == 'authorized':
                    xml_rec.create_file_authorized()
            try:
                # el webservice en mensajes a veces devuelve un texto vacio
                if doc.mensajes:
                    if isinstance(doc.mensajes.mensaje, list):
                        for msj in doc.mensajes.mensaje:
                            msj_res.append({'identificador': msj.identificador if hasattr(msj, 'identificador') else u'',
                                            'informacionAdicional': msj.informacionAdicional if hasattr(msj, 'informacionAdicional') else u'',
                                            'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else u'',
                                            'tipo': msj.tipo if hasattr(msj, 'tipo') else u'',
                                            })
                    else:
                        for msj in doc.mensajes:
                            msj_res.append({'identificador': msj.identificador if hasattr(msj, 'identificador') else u'',
                                            'informacionAdicional': msj.informacionAdicional if hasattr(msj, 'informacionAdicional') else u'',
                                            'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else u'',
                                            'tipo': msj.tipo if hasattr(msj, 'tipo') else u'',
                                            })
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(
                    u"Can\'t process messages %s. ERROR: %s", doc.mensajes, error)
        return ok, msj_res

    def create_file_authorized(self):
        for xml_data in self:
            # el xml debe estar autorizado, tener fecha de autorizacion
            # si tengo xml firmado, a ese anexarle la autorizacion
            if xml_data.state == 'authorized' and xml_data.xml_authorization and xml_data.file_signed_path:
                tree = etree.parse(self.generate_file_name(
                    xml_data.id, 'file_signed'))
                root = etree.Element("autorizacion")
                authorizacion_ele = etree.Element('estado')
                authorizacion_ele.text = "AUTORIZADO"
                root.append(authorizacion_ele)
                # anexar la fecha y numero de autorizacion
                authorizacion_ele = etree.Element('numeroAutorizacion')
                authorizacion_ele.text = xml_data.xml_authorization
                root.append(authorizacion_ele)
                authorizacion_ele = etree.Element('fechaAutorizacion')
                authorizacion_ele.text = xml_data.authorization_date or time.strftime(
                    DTF)
                root.append(authorizacion_ele)
                authorizacion_ele = etree.Element('ambiente')
                authorizacion_ele.text = "PRODUCCION" if xml_data.type_environment == 'production' else 'PRUEBAS'
                root.append(authorizacion_ele)
                # agregar el resto del xml
                root.append(tree.getroot())
                xml_authorized = tostring(root)
                file_authorized_path = self.write_file(
                    xml_data.id, 'file_authorized', xml_authorized)
                xml_data.write({'file_authorized_path': file_authorized_path, })
        return True

    @api.model
    def _ger_url_ws(self, environment, url_type):
        """
        Retorna la url para pruebas o produccion segun el tipo de ambiente
        @param url_type: el tipo de url a solicitar, puede ser:
            reception: url para recepcion de documentos
            authorization: url para autorizacion de documentos
        """
        company = self.env.user.company_id
        url_data = ""
        # pruebas
        if environment == '1':
            if url_type == 'reception':
                url_data = company.ws_receipt_test
            elif url_type == 'authorization':
                url_data = company.ws_auth_test
        elif environment == '2':
            if url_type == 'reception':
                url_data = company.ws_receipt_production
            elif url_type == 'authorization':
                url_data = company.ws_auth_production
        return url_data

    def test_send_check_state(self):
        company = self.env.user.company_id
        environment = self._get_environment(company)
        xml_field = 'file_signed'
        max_intentos = 1
        for xml_rec in self:
            xml_rec.with_context(no_send=True).send_xml_data_to_check(
                xml_rec.id, environment, xml_field, max_intentos)
        return True

    @api.model
    def send_xml_data_to_check(self, xml_id, environment, xml_field='file_signed', max_intentos=1):
        """Envia al web service indicado el xml a ser verificado
        :paran xml_id: Objeto a escribir
        :param environment: Puede ser los siguientes ambientes :
            1 : Pruebas
            2 : Produccion
        :param xml_field: este debe ser
            xml_signed_file : Archivo Firmado
        :rtype: code of message
        """
        def _check_intentos(context=None):
            if not context:
                context = {}
            # si supero el maximo de intentos liberar la clave actual y generar una en modo contingencia
            # una tarea cron debe encargarse de reenviar para autorizar
            if max_intentos > company.max_intentos:
                # pasar por context que el modo de emision es contingencia
                # si el documento esta en espera de autorizacion no pasar a contingencia
                if not context.get('cron_process', False) and xml_rec.state != 'waiting':
                    ctx['emission'] = '2'
                    xml_rec._free_key_in_use()
                    xml_rec.with_context(ctx).text_write_binary()
            elif send_again:
                # si no supera el maximo de intentos, volve a intentar
                return self.send_xml_data_to_check(xml_id, environment, xml_field, max_intentos=max_intentos + 1)
            return True
        company = self.env.user.company_id
        xml_rec = self.browse(xml_id)
        ctx = self.env.context.copy()
        send_again, authorized, raise_error = False, False, True
        messages_error, message_data = [], []
        # TODO: si es emitido por contingencia, no puedo enviarlo,
        # la tarea cron debe encargarse de eso
        if xml_rec.state == 'contingency' and not self.env.context.get('no_send', False):
            return True
        # si esta esperando autorizacion, una tarea cron debe encargarse de eso
        if xml_rec.state == 'waiting' and not self.env.context.get('no_send', False):
            return True
        ws_receipt = self._ger_url_ws(environment, 'reception')
        type_url = environment == '1' and 'test' or 'production'
        if ws_receipt:
            try:
                receipt_client = self.get_current_wsClient(
                    'ws_receipt_' + type_url)
                auth_client = self.get_current_wsClient('ws_auth_' + type_url)
                response = self._send_xml_data_to_valid(
                    xml_id, xml_field, receipt_client, auth_client)
                res_ws_valid, msj, raise_error, previous_authorized = self._process_response_check(
                    xml_id, response)
                message_data.extend(msj)
                # si no hay respuesta, el webservice no esta respondiendo, la tarea cron se debe encargar de este proceso
                # solo cuando no hay errores, si hay errores el webservice esta respondiendo y debo mostrar los msj al usuario
                if not res_ws_valid and not raise_error:
                    send_again = True
                elif res_ws_valid and not previous_authorized:
                    response_auth = self._send_xml_data_to_autorice(
                        xml_id, xml_field, auth_client)
                    # si el sri no me respondio o no es la respuesta que esperaba
                    # verificar si quedo en procesamiento antes de volver a autorizar
                    if not response_auth or isinstance(response_auth.autorizaciones, (str)):
                        response_check = self._send_xml_data_to_valid(
                            xml_id, xml_field, receipt_client, auth_client)
                        res_ws_valid, msj, raise_error, previous_authorized = self._process_response_check(
                            xml_id, response_check)
                        # si se intento una vez mas y no se pudo autorizar , dejar el documento en espera de autorizacion para que la tarea cron se encargue de eso
                        if not res_ws_valid and not previous_authorized:
                            xml_rec.write({'state': 'waiting'})
                    else:
                        authorized, msj = self._process_response_autorization(
                            xml_id, response_auth)
                        message_data.extend(msj)
                messages_error, raise_error = self._create_messaje_response(
                    xml_id, message_data, authorized, raise_error)
            except Exception as e:
                xml_rec.write({'state': 'rejected'})
                # FIX: pasar a unicode para evitar problemas
                error = self._clean_str(tools.ustr(e))
                _logger.warning(
                    u"Error send xml to server %s. ERROR: %s", ws_receipt, error)
                send_again = True
        if send_again:
            return _check_intentos(self.env.context)
        # si llamo de tarea cron, no mostrar excepcion para que se creen los mensajes
        if self.env.context.get('call_from_cron', False):
            raise_error = False
        # si estoy en produccion y tengo errores lanzar excepcion, en pruebas no lanzar excepcion
        if messages_error and raise_error and environment == '2':
            # TODO: en flujo de datos se mensiona que se debe mostrar los errores recibidos al autorizar
            # pero si lanzo excepcion se revierte toda la transaccion realizada, siempre sera asi
            # o encontrar manera de mostrar mensajes al usuario sin revertir transaccion(a manera informativa)
            messages_error.insert(
                0, u"No se pudo autorizar, se detalla errores recibidos")
            raise Warning(_(u"\n".join(messages_error)))
        return authorized

    @api.model
    def __get_variables_availables(self, document, invoice_type):
        util_model = self.env['ecua.utils']
        res = {}
        # TODO: agregar demas campos disponibles
        res['Cliente'] = document.partner_id.display_name
        res['TipoDocumento'] = util_model.get_selection_item(
            'sri.mail.message', 'document_type', invoice_type)
        res['NumeroDocumento'] = document.document_number
        res['NumeroAutorizacion'] = document['electronic_authorization_sri']
        res['FechaAutorizacion'] = document.xml_data_id.authorization_date
        res['Usuario'] = document.partner_id.electronic_user
        res['Password'] = document.partner_id.electronic_password
        return res

    @api.model
    def get_message(self, document_id, invoice_type):
        """
        Devuelve el mensaje para enviar por mail, segun el tipo de documento
        :param document_id: int, id del documento
        :param invoice_type: Puede ser los tipos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
        :rtype: dict keys ['xml_file','report_file','message_mail','message_first','email_to]
        """
        ctx = self.env.context.copy()
#         ctx['no_objects'] = True
        util_model = self.env['ecua.utils']
        message_model = self.env['sri.mail.message']
        partner_mail_model = self.env['res.partner.mail']
        res = {'xml_file': '',
               'report_file': '',
               'message_mail': '',
               'message_first': '',
               'email_to': [],
               }
        document_type = modules_mapping.get_document_type(invoice_type)
        model_name = modules_mapping.get_model_name(document_type)
        message_recs = message_model.search(
            [('document_type', '=', invoice_type)])
        if message_recs and model_name:
            document = self.env[model_name].browse(document_id)
            valiables_availables = self.__get_variables_availables(
                document, invoice_type)
            # TODO: agregar url
            valiables_availables['url'] = ''
            message = message_recs[0]
            # TODO: hacer el parser de las variables
            res['message_mail'] = message.name % valiables_availables
            # si nunca se ha conectado, enviar datos de conexion para el cliente
            if not document.partner_id.last_conection and message.message_first:
                res['message_first'] = message.message_first % valiables_availables
            # obtener los mails
            if document.partner_id:
                res['email_to'] = partner_mail_model.get_email_to_partner(
                    document.partner_id.id, invoice_type)
            # generar el reporte
            report_name = REPORT_NAME[invoice_type]
            file_name_report = report_name + document.document_number
            ctx['active_ids'] = [document_id]
            ctx['active_id'] = document_id
            ctx['active_model'] = model_name
            res['report_file'] = util_model.with_context(ctx).create_report(
                [document_id], report_name, model_name, file_name_report)[0]
        return res

    @api.model
    def get_info_xml_to_partner(self, document_id, invoice_type='out_refund'):
        """Devuelve el xml y el pdf para enviarlo por mail al cliente
        @param document_id: int, id del documento
        :param invoice_type: Puede ser los siguientes modelos :
            out_invoice : Factura
            out_refund : Nota de Credito
            debit_note_out : Nota de Debito
            delivery_note : Guia de Remision
            withhold_purchase : Comprobante de Retencion
        @return: dict: keys: ['xml_file','report_file','message_mail','message_first','email_to]
        """
        res = {'xml_file': '',
               'report_file': '',
               'message_mail': '',
               'message_first': '',
               'email_to': [],
               }
        sri_xml_recs = self.get_xml_data_id(document_id, invoice_type)
        if sri_xml_recs:
            sri_xml = sri_xml_recs
            document = sri_xml[FIELDS_NAME[invoice_type]]
            res.update(self.get_message(document_id, invoice_type))
            # TODO: obtener el xml
            file_name_report = REPORT_NAME[invoice_type] + \
                document.document_number
            xml_file = self.get_file(sri_xml.id, 'file_authorized')
            if xml_file:
                res['xml_file'] = (file_name_report + ".xml",
                                   base64.encodestring(xml_file))
        return res

    @api.model
    def _check_totales(self, xml_data, document, document_type):
        notification_task_model = self.env['util.notification.task']
        mod_model = self.env['ir.model.data']
        task_recs = self.env['util.notification.task'].browse()
        document_name, document_number = "", ""
        total_erp, total_importado = 0.0, 0.0
        notification_id = mod_model.xmlid_to_res_id(
            'ecua_documentos_electronicos.not_elect_002', False)
        if notification_id:
            try:
                external_data = eval(xml_data.external_data)
            except:
                external_data = {}
            # solo verificar de facturas de clientes y retenciones
            if external_data and document_type in ('withhold', 'out_invoice'):
                # factura de cliente
                if document_type == 'out_invoice':
                    document_name = "Factura"
                    document_number = document.document_number
                    total_erp = document.amount_total
                    total_importado = float(
                        external_data.get('importe_total', 0.0))
                elif document_type == 'withhold':
                    document_name = "Retencion"
                    document_number = document.document_number
                    total_erp = document.total
                    total_importado = 0.0
                    for line in external_data.get('lineas_retencion', []):
                        total_importado += float(line.get('valor_retenido', 0.0))
                # permitir una tolerancia de 10 centavos
                if float_compare(abs(total_erp - total_importado), 0.01, precision_digits=2) > 0:
                    message = '<br><b>%s %s</b> No coinciden los totales. Calculado ERP: %s Importado: %s' % \
                        (document_name, document_number, total_erp, total_importado)
                    task_recs += notification_task_model.create({'notification_id': notification_id,
                                                                 'message': message,
                                                                 })
        return task_recs

    def text_write_binary(self):
        task_recs = self.env['util.notification.task'].browse()
        notification_task_recs = self.env['util.notification.task'].browse()
        new_ids = []
        for xml_rec in self:
            # procesar los modelos que son de account.invoice(facturas, NC, ND)
            invoice_type = ""
            # factura
            res_document = xml_rec.invoice_out_id
            # NC
            if not res_document:
                res_document = xml_rec.credit_note_out_id
            # ND
            if not res_document:
                res_document = xml_rec.debit_note_out_id
            if res_document:
                invoice_type = modules_mapping.get_invoice_type(
                    res_document.type, res_document.debit_note, res_document.liquidation)
            elif xml_rec.withhold_id:
                res_document = xml_rec.withhold_id
                invoice_type = 'withhold_purchase'
            elif xml_rec.delivery_note_id:
                res_document = xml_rec.delivery_note_id
                invoice_type = 'delivery_note'
            if res_document and invoice_type:
                try:
                    if xml_rec.external_document and self.env.context.get('call_from_cron', False):
                        task_recs = self._check_totales(
                            xml_rec, res_document, invoice_type)
                        if task_recs:
                            notification_task_recs += task_recs
                            continue
                    new_ids.append(xml_rec.id)
                    string_data, binary_data = self.generate_xml_file(
                        xml_rec.id, res_document.id, invoice_type, 'individual')
                    file_xml_path = self.write_file(
                        xml_rec.id, 'file_xml', string_data)
                    xml_rec.write({'file_xml_path': file_xml_path})
                except odoo.osv.osv.except_osv:
                    raise
                except ValidationError:
                    raise
                except Warning:
                    raise
                except except_orm:
                    raise
                except Exception as e:
                    error = self._clean_str(tools.ustr(e))
                    _logger.warning(
                        u"Error function text_write_binary. ERROR: %s", error)
        self.send_mail_document_wrong_total(notification_task_recs)
        return new_ids

    @api.model
    def send_mail_document_wrong_total(self, notification_task_recs):
        notification_task_model = self.env['util.notification.task']
        mod_model = self.env['ir.model.data']
        util_model = self.env['ecua.utils']
        if not notification_task_recs:
            notification_id = mod_model.xmlid_to_res_id(
                'ecua_documentos_electronicos.not_elect_002', False)
            if notification_id:
                # buscar las notificaciones pendientes
                notification_task_recs = notification_task_model.search([('notification_id', '=', notification_id),
                                                                         ('state', '=',
                                                                          'pending'),
                                                                         ])
        if notification_task_recs:
            # agrupar los mensajes por defecto
            messages = notification_task_model.get_messages(
                notification_task_recs.ids, True).values()
            for message_mail in messages:
                util_model.send_notification_email(
                    'not_elect_002', 'ecua_documentos_electronicos', content=message_mail)
            notification_task_recs.write({'state': 'done'})
        return True

    def test_sing_xml_file(self):
        def _print_error(er):
            if xml_rec.external_document:
                error = self._clean_str(tools.ustr(er))
                _logger.warning(
                    u"Error sing xml data ID: %s. ERROR: %s", xml_rec.id, error)
            else:
                raise

        company = self.env.user.company_id
        if tools.config.get('no_electronic_documents') and company.type_environment == 'production':
            return True
        ws_signer = Client(company.ws_signer)
        for xml_rec in self:
            vals = {}
            try:
                if not company.key_type_id:
                    if company.type_environment == 'production':
                        raise Warning(
                            _(u"Es obligatorio seleccionar el tipo de llave o archivo de cifrado usa para la firma de los documentos electrónicos, verificar la configuración de la compañia"))
                    else:
                        _logger.warning(
                            u"Error key type doesn't configured correctly in company, please verify")
                        return False
                # obtener el archivo con la clave
                cert_path = 'null'
                cert_type = 'PKCS11'
                if company.key_type_id.key_type == 'file':
                    cert_type = 'PKCS12'
                    if company.key_type_id.path:
                        cert_path = company.key_type_id.path
                    else:
                        cert_file_name = "sample_cert.p12"
                        cert_path = os.path.join(
                            'ecua_documentos_electronicos', 'data', 'xml_samples', cert_file_name)
                # TODO: deberia guardarse cifrada la clave
                cert_pass = company.key_password
                adps = odoo.modules.module.ad_paths
                if cert_path:
                    for adp in adps:
                        pt = os.path.join(adp, cert_path)
                        pt = os.path.normpath(pt)
                        if os.path.isfile(pt):
                            cert_path = pt
                            break
                if xml_rec.file_xml_path:
                    xml_string_data = self.get_file(xml_rec.id, 'file_xml')
                    xml_signed = ws_signer.service.signXmlFile(
                        xml_string_data.decode(), cert_path, cert_pass, cert_type)
                    file_signed_path = self.write_file(
                        xml_rec.id, 'file_signed', str.encode(xml_signed))
                    vals = {
                        'file_signed_path': file_signed_path,
                        'signed_date': time.strftime(DTF),
                    }
                # si esta en contingencia, no cambiar de estado, para que la tarea cron sea el que procese estos registros
                vals['state'] = 'signed'
                if vals:
                    xml_rec.write(vals)
            except odoo.osv.osv.except_osv as eo:
                _print_error(eo)
            except ValidationError as ve:
                _print_error(ve)
            except Warning as w:
                _print_error(w)
            except except_orm as eor:
                _print_error(eor)
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(
                    u"Error sing xml data ID: %s. ERROR: %s", xml_rec.id, error)
        return True

    def test_send_file(self):
        company = self.env.user.company_id
        environment = self._get_environment(company)
        for xml_rec in self:
            # TODO: tomar el tipo de ambiente segun configuracion, no 1 estatico
            self.send_xml_data_to_check(xml_rec.id, environment, 'file_signed')
        return True

    @api.model
    def check_retention_asumida(self, document, invoice_type):
        if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out'):
            if document.fiscal_position_id and document.fiscal_position_id.retencion_asumida:
                return True
        if document.partner_id and document.partner_id.property_account_position_id and document.partner_id.property_account_position_id.retencion_asumida:
            return True
        return False

    def test_send_mail_partner(self):
        mail_model = self.env['sri.mail.util']
        invoice_type = ''
        documents_sended = {}
        documents_no_sended = {}
        for xml_rec in self:
            invoice_type = ''
            document = False
            # obtener el tipo de documento para validarlo con el esquema correcto
            if xml_rec.invoice_out_id:
                invoice_type = 'out_invoice'
                document = xml_rec.invoice_out_id
            elif xml_rec.credit_note_out_id:
                invoice_type = 'out_refund'
                document = xml_rec.credit_note_out_id
            elif xml_rec.debit_note_out_id:
                invoice_type = 'debit_note_out'
                document = xml_rec.debit_note_out_id
            elif xml_rec.delivery_note_id:
                invoice_type = 'delivery_note'
                document = xml_rec.delivery_note_id
            elif xml_rec.withhold_id:
                invoice_type = 'withhold_purchase'
                document = xml_rec.withhold_id
            elif xml_rec.xml_type == 'grouped':
                invoice_type = 'lote_masivo'
            if document:
                retencion_asumida = self.check_retention_asumida(
                    document, invoice_type)
                if retencion_asumida:
                    if self.env.context.get('from_function'):
                        documents_sended[xml_rec.id] = True
                        continue
                    else:
                        return True
            try:
                # al consumidor final no se debe enviar mail, pero marcarlo como enviado
                if xml_rec.partner_id and xml_rec.partner_id.type_ref == 'consumidor':
                    documents_sended[xml_rec.id] = True
                    continue
                compose_data = {}
                if invoice_type in ('out_invoice', 'out_refund', 'debit_note_out'):
                    compose_data = document.action_invoice_sent()
                elif invoice_type == 'withhold_purchase':
                    compose_data = document.action_withhold_sent()
                elif invoice_type == 'delivery_note':
                    continue
                if compose_data.get('res_model', False):
                    wizard_model = self.env[compose_data.get(
                        'res_model', False)]
                    wizard = wizard_model.with_context(
                        compose_data.get('context')).create({})
                    wizard.onchange_template_id_wrapper()
                    wizard.send_mail_action()
                    documents_sended[xml_rec.id] = True
                    xml_rec.write({
                        'send_mail': True,
                    })
                else:
                    documents_no_sended[xml_rec.id] = True
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(u"Error send mail to partner. ERROR: %s", error)
                documents_no_sended[xml_rec.id] = True
        if self.env.context.get('from_function', False):
            return documents_sended.keys(), documents_no_sended.keys()
        else:
            return True

    def process_document_electronic(self):
        """
        Funcion para procesar los documentos(crear xml, firmar, autorizar y enviar mail al cliente)
        """
        send_file = True
        # para los documentos electronicos firmados que son documentos externos,
        # no debe enviarlo a autorizar, para esto existira otra tarea cron y asi ganar en rendimiento
        if 'sign_now' in self.env.context and not self.env.context.get('sign_now', False):
            send_file = False
        # si se hace el proceso electronico completamente
        if send_file:
            # enviar a crear el xml
            self.text_write_binary()
            # enviar a firmar el xml
            self.test_sing_xml_file()
            # enviar a autorizar el xml(si se autorizo, enviara el mail a los involucrados)
            self.test_send_file()
        else:
            # solo enviar a crear el xml con la clave de acceso,
            # una tarea cron se debe encargar de calcular datos calculados y continuar con el proceso electronico
            self.text_write_binary()
        return True

    @api.model
    def send_documents_contingency(self):
        """
        Procesar los documentos emitidos en modo contingencia
        """
        document = False
        res_model_name = ""
        ctx = self.env.context.copy()
        ctx_invoice = self.env.context.copy()
        company = self.env.user.company_id
        invoice_line_model = self.env['account.invoice.line']
        # pasar flag para que al firmar el documento, y estaba en contingencia, me cambie el estado
        ctx['skip_contingency'] = True
        ctx['call_from_cron'] = True
        ctx['cron_process'] = True
        # No se debe verificar constantemente en que estado esta
        ctx['emission'] = '1'
        xml_recs = self.search(
            [('state', '=', 'contingency')], limit=company.cron_process)
        # los documentos externos solo creo la data, pero no se hace el calculo de campos funcionales
        # hacer el calculo antes de enviar al proceso electronico
        for xml_rec in xml_recs:
            # si no es documento externo, no calcular impuestos
            # solo documentos externos debo calcular impuestos antes de procesar el documento
            if not xml_rec.external_document:
                continue
            # si los campos del modelo referencial ya fueron calculados
            # no volver a calcularlos, para optimizar rendimiento
            if xml_rec.fields_function_calculate:
                continue
            # enviar a generar el reporte, obtener los datos necesarios
            if xml_rec.invoice_out_id:
                document = xml_rec.invoice_out_id
                res_model_name = 'account.invoice'
            elif xml_rec.credit_note_out_id:
                document = xml_rec.credit_note_out_id
                res_model_name = 'account.invoice'
            elif xml_rec.debit_note_out_id:
                document = xml_rec.debit_note_out_id
                res_model_name = 'account.invoice'
            elif xml_rec.withhold_id:
                document = xml_rec.withhold_id
                res_model_name = 'l10n_ec.withhold'
            elif xml_rec.delivery_note_id:
                document = xml_rec.delivery_note_id
                res_model_name = 'l10n_ec.delivery.note'
            if document and res_model_name:
                ctx_invoice['active_ids'] = [document.ids]
                ctx_invoice['active_id'] = document.id
                # si es facturas enviar a calcular los campos calculados de las lineas
                # luego los campos calculados de la factura
                # y por ultimo enviar a calcular los impuestos
                if res_model_name == 'account.invoice':
                    invoice_line_recs = invoice_line_model.search(
                        [('invoice_id', '=', document.id)])
                    if invoice_line_recs:
                        invoice_line_recs.write({})
                document.with_context(ctx_invoice).write({})
                if res_model_name == 'account.invoice':
                    document.with_context(ctx_invoice).button_reset_taxes()
                xml_rec.write({'fields_function_calculate': True})
        # TODO: debo cambiar la clave de contingecia antes de reanudar el proceso o no???
        # si es asi, cambiarla antes de llamar a la funcion, ya que si tiene clave, trabaja sobre esa clave
        xml_recs.with_context(ctx).process_document_electronic()
        return True

    @api.model
    def _update_invoice_line_vals(self, invoice_line_id, values, company, company_currency):
        SQL = """UPDATE account_invoice_line il 
                    SET price_unit_final = %(price_unit_final)s,
                        price_subtotal = %(price_subtotal)s,
                        base_no_iva = %(base_no_iva)s,
                        base_iva = %(base_iva)s,
                        base_iva_0 = %(base_iva_0)s,
                        total_retencion = %(total_retencion)s,
                        total_iva = %(total_iva)s
                WHERE il.id = %(invoice_line_id)s
            """
        self.env.cr.execute(SQL, {'invoice_line_id': invoice_line_id,
                                  'price_unit_final': company_currency.round(values['price_unit_final']),
                                  'price_subtotal': company_currency.round(values['total']),
                                  'base_no_iva': company_currency.round(values['base_no_iva']),
                                  'base_iva': company_currency.round(values['base_iva']),
                                  'base_iva_0': company_currency.round(values['base_iva_0']),
                                  'total_retencion': company_currency.round(values['total_retencion_iva'] + values['total_retencion_renta']),
                                  'total_iva': company_currency.round(values['total_iva']),
                                  })
        return True

    @api.model
    def _update_invoice_vals(self, invoice_id, values, company, company_currency):
        # actualizar valores en la factura y marcarla como abierta
        SQL = """UPDATE account_invoice i
                    SET amount_untaxed = %(amount_untaxed)s,
                        amount_tax = %(amount_tax)s,
                        amount_total = %(amount_total)s,
                        residual = %(amount_total)s,
                        base_iva = %(base_iva)s,
                        base_no_iva = %(base_no_iva)s,
                        base_iva_0 = %(base_iva_0)s,
                        total_ice = %(total_ice)s,
                        total_sin_descuento = %(total_sin_descuento)s,
                        total_retencion_iva = %(total_retencion_iva)s,
                        total_retencion_renta = %(total_retencion_renta)s,
                        total_retencion = %(total_retencion)s,
                        total_iva = %(total_iva)s,
                        total_descuento = %(total_descuento)s,
                        total_con_impuestos = %(total_con_impuestos)s
                WHERE i.id = %(invoice_id)s
            """
        self.env.cr.execute(SQL, {'invoice_id': invoice_id,
                                  'amount_untaxed': company_currency.round(values['amount_untaxed']),
                                  'amount_tax': company_currency.round(values['amount_tax']),
                                  'amount_total': company_currency.round(values['amount_untaxed'] + values['amount_tax']),
                                  'base_iva': company_currency.round(values['base_iva']),
                                  'base_no_iva': company_currency.round(values['base_no_iva']),
                                  'base_iva_0': company_currency.round(values['base_iva_0']),
                                  'total_ice': company_currency.round(values['total_ice']),
                                  'total_sin_descuento': company_currency.round(values['total_sin_descuento']),
                                  'total_retencion_iva': company_currency.round(values['total_retencion_iva']),
                                  'total_retencion_renta': company_currency.round(values['total_retencion_renta']),
                                  'total_retencion': company_currency.round(values['total_retencion_iva'] + values['total_retencion_renta']),
                                  'total_iva': company_currency.round(values['total_iva']),
                                  'total_descuento': company_currency.round(values['total_descuento']),
                                  'total_con_impuestos': company_currency.round(values['total_con_impuestos']),
                                  })
        return True

    @api.model
    def _create_invoice_tax(self, invoice_id, values, company, company_currency):
        for taxe in values:
            # En nuestra legislacion se descartan los decimales despues del 3 digito para redondear
            taxe['base'] = company_currency.round(
                trunc_decimal(taxe['base'], 3))
            taxe['amount'] = company_currency.round(
                trunc_decimal(taxe['amount'], 3))
            taxe['base_amount'] = company_currency.round(
                trunc_decimal(taxe['base_amount'], 3))
            taxe['tax_amount'] = company_currency.round(
                trunc_decimal(taxe['tax_amount'], 3))
            invoice_tax_data = taxe.copy()
            invoice_tax_data.update({
                'manual': False,
                'create_uid': self.env.uid,
                'write_uid': self.env.uid,
                'base_code_id': taxe.get('base_code_id') and taxe.get('base_code_id', None) or None,
                'tax_code_id': taxe.get('tax_code_id') and taxe.get('tax_code_id', None) or None,
                'account_analytic_id': taxe.get('account_analytic_id') and taxe.get('account_analytic_id', None) or None,
                'company_id': company.id,
            })
            fields1 = ''
            fields2 = ''
            for key in invoice_tax_data:
                fields1 += key + ','
                fields2 += '%(' + key + ")s,"
            SQL = """INSERT INTO account_invoice_tax
                    (""" + fields1 + """ create_date, write_date) 
                    VALUES( """ + fields2 + """ now() at time zone 'UTC', now() at time zone 'UTC')
                """
            self.env.cr.execute(SQL, invoice_tax_data)
        return True

    @api.model
    def send_external_documents(self):
        """
        Procesar los documentos emitidos por procesos externos
        """
        return True

    @api.model
    def send_documents_waiting_autorization(self):
        """
        Procesar documentos que no fueron autorizados 
        pero recibieron error 70(en espera de autorizacion)
        los cuales no debe volver a enviar a autorizar, 
        solo esperar que sean confirmada su autorizacion
        """
        def _get_header(caption):
            header = []
            header.append("<table border=1>")
            header.append("<caption>%s</caption>" % caption)
            header.append("<tr>")
            header.append(_(u"<td><b>Mensage</b></td>"))
            header.append(_(u"<td><b>Información Adicional</b></td>"))
            header.append("</tr>")
            return header
        util_model = self.env['ecua.utils']
        company = self.env.user.company_id
        xml_recs = self.search([('state', '=', 'waiting')])
        # en algunas ocaciones los documentos se envian a autorizar, pero se quedan como firmados
        # buscar los documentos firmados que se hayan enviado a autorizar para verificar si fueron autorizados o no
        xml_signed_recs = self.search([('state', '=', 'signed')])
        xml_send_to_autorice = False
        for xml_signed in xml_signed_recs:
            xml_send_to_autorice = False
            for send_try in xml_signed.try_ids:
                # si hay un intento de envio a autorizar, verificar si el registro fue autorizado
                if send_try.type_send == 'send':
                    xml_send_to_autorice = True
                    break
            # agregarlo a la lista para verificar si fue autorizado
            if xml_send_to_autorice and xml_signed not in xml_recs:
                xml_recs += xml_signed
                continue
        xml_field = 'file_signed'
        ctx = self.env.context.copy()
        # pasar flag para que en caso de no autorizar, no me cambie estado del documento y seguir intentado
        ctx['no_change_state'] = True
        message_mail = []
        send_mail = False
        name = ""
        field_name = ""
        type_environment = self._get_environment(
            company) == '1' and 'test' or 'production'
        receipt_client = self.get_current_wsClient(
            'ws_receipt_' + type_environment)
        auth_client = self.get_current_wsClient('ws_auth_' + type_environment)
        for xml_data in xml_recs:
            name = ""
            if xml_data.invoice_out_id:
                field_name = 'invoice_out_id'
                name += "Factura: "
            elif xml_data.credit_note_out_id:
                field_name = 'credit_note_out_id'
                name += "Nota de credito: "
            elif xml_data.debit_note_out_id:
                field_name = 'debit_note_out_id'
                name += "Nota de debito: "
            elif xml_data.delivery_note_id:
                field_name = 'delivery_note_id'
                name += "Guia de Remision: "
            elif xml_data.withhold_id:
                field_name = 'withhold_id'
                name += "Retencion: "
            if field_name:
                name += xml_data[field_name].document_number
            response = self._send_xml_data_to_valid(
                xml_data.id, xml_field, receipt_client, auth_client)
            ok, messages, raise_error, previous_authorized = self._process_response_check(
                xml_data.id, response)
            # si recibio la solicitud, enviar a autorizar
            if ok:
                response = self.with_context(ctx)._send_xml_data_to_autorice(
                    xml_data.id, xml_field, auth_client)
                ok, messages = self.with_context(
                    ctx)._process_response_autorization(xml_data.id, response)
            self.with_context(ctx)._create_messaje_response(
                xml_data.id, messages, ok, raise_error)
            # TODO: si no se puede autorizar, que se debe hacer??
            # por ahora, no hago nada para que la tarea siga intentando en una nueva llamada
            if not ok and messages:
                send_mail = True
                message_mail.extend(_get_header(name))
                for msj in messages:
                    message_mail.append("<tr>")
                    message_mail.append("<td>%s</td>" % msj.get('mensaje', ''))
                    message_mail.append("<td>%s</td>" %
                                        msj.get('informacionAdicional', ''))
                    message_mail.append("</tr>")
                message_mail.append("</table><br>")
        if send_mail:
            util_model.send_notification_email(
                'not_elect_001', 'ecua_documentos_electronicos', "".join(message_mail), '', '', [], '')
        return True

    @api.model
    def process_external_document(self, document_data, clave_acceso='', sign_now=True, preload_data=None):
        """
        Procesa, firma y autoriza documentos electronicamente
        @param document_data: Lista de diccionario con los datos a procesar
        @param clave_acceso: clave de acceso en modo contingencia, cuando el cliente genero el documento en ese ambiente
        @param sign_now: indica si el documento se debe firmar y autorizar o la autorizacion se debe hacer posteriormente
        @param preload_data: Se usa para permitir a otros procesos de importacion procesar el documento de factura
        @return: dict con valores:
                    numAutorizacion: str numero de autorizacion obtenida desde el SRI 
                    fechaAutorizacion: datetime fecha en que se realizo la autorizacion
                    claveAcceso: str clave de acceso generada para el documento
                    mensajes: lista de dict con los mensajes generados durante todo el proceso
                        codigo: codigo del mensaje
                        descripcion: descripcion del mensaje
                        tipo: tipo de mensaje, puede ser(info, warning, error) 
        """
        numAutorizacion = ""
        fechaAutorizacion = time.strftime('%Y-%m-%d')
        claveAcceso = ""
        mensajes = []
        res = {'numAutorizacion': numAutorizacion,
               'fechaAutorizacion': fechaAutorizacion,
               'claveAcceso': claveAcceso,
               'mensajes': mensajes,
               }
        return res

    @api.model
    def get_external_xml_file(self, clave_acceso="", autorizacion=""):
        """
        Obtener el archivo xml firmado y autorizado
        @param clave_acceso: Clave de acceso del documento relacionado
        @param autorizacion: Autorizacion dada por el SRI al documento relacionado
        @return: dict: file, file_name, mensajes
                file: archivo xml en base64
                file_name: str, nombre del archivo
                mensajes: lista de mensajes
        """
        args = []
        file_name = 'xml_autorizado'
        if clave_acceso:
            args.append(('xml_key', '=', clave_acceso))
            file_name += "_" + clave_acceso
        if autorizacion:
            args.append(('xml_authorization', '=', autorizacion))
            file_name += "_" + autorizacion
        file_name += '.xml'
        # TODO: agregar estado para buscar???
#         args.append(('state','in',('authorized',)))
        field_name = 'file_authorized'
        res = {'file': "",
               'file_name': file_name,
               'mensajes': []
               }
        if args:
            xml_recs = self.search(args, limit=1)
            if not xml_recs:
                res['mensajes'].append(
                    'No se encontro archivo con los datos facilitados')
            else:
                res['file'] = base64.encodestring(
                    self.get_file(xml_recs[0].id, field_name))
        return res

    @api.model
    def get_external_pdf_report(self, clave_acceso="", autorizacion=""):
        """
        Obtener el archivo pdf del reporte
        @param clave_acceso: Clave de acceso del documento relacionado
        @param autorizacion: Autorizacion dada por el SRI al documento relacionado
        @return: dict: file, file_name, mensajes
                file: archivo pdf en base64
                file_name: str, nombre del archivo
                mensajes: lista de mensajes
        """
        util_model = self.env['ecua.utils']
        args = []
        if clave_acceso:
            args.append(('xml_key', '=', clave_acceso))
        if autorizacion:
            args.append(('xml_authorization', '=', autorizacion))
        # TODO: agregar estado???
        res = {'file': "",
               'file_name': 'report_pdf.pdf',
               'mensajes': []
               }
        model = ''
        report_name = ''
        file_name = 'report_electronic'
        file_report = []
        res_id = False
        ctx = self.env.context.copy()
        if args:
            xml_recs = self.search(args, limit=1)
            if not xml_recs:
                res['mensajes'].append(
                    'No se encontro archivo con los datos facilitados')
            else:
                xml_data = xml_recs[0]
                # enviar a generar el reporte, obtener los datos necesarios
                if xml_data.invoice_out_id:
                    res_id = xml_data.invoice_out_id.id
                    model = 'account.invoice'
                    report_name = 'e_invoice'
                    file_name = 'Factura_%s' % xml_data.invoice_out_id.document_number
                elif xml_data.credit_note_out_id:
                    res_id = xml_data.credit_note_out_id.id
                    model = 'account.invoice'
                    report_name = 'e_credit_note'
                    file_name = 'NotaCredito_%s' % xml_data.credit_note_out_id.document_number
                elif xml_data.debit_note_out_id:
                    res_id = xml_data.debit_note_out_id.id
                    model = 'account.invoice'
                    report_name = 'e_debit_note'
                    file_name = 'NotaDebito_%s' % xml_data.debit_note_out_id.document_number
                elif xml_data.withhold_id:
                    res_id = xml_data.withhold_id.id
                    model = 'l10n_ec.withhold'
                    report_name = 'e_retention'
                    file_name = 'Retencion_%s' % xml_data.withhold_id.document_number
                elif xml_data.delivery_note_id:
                    res_id = xml_data.delivery_note_id.id
                    model = 'l10n_ec.delivery.note'
                    report_name = 'e_delivery_note'
                    file_name = 'GuiaRemision_%s' % xml_data.delivery_note_id.document_number
                if res_id and model and report_name:
                    ctx['active_ids'] = [res_id]
                    ctx['active_id'] = res_id
                    file_report = util_model.with_context(ctx).create_report(
                        [res_id], report_name, model, file_name)
                    if file_report:
                        res['file'] = base64.encodestring(file_report[0][1])
                        res['file_name'] = file_report[0][0]
                else:
                    res['mensajes'].append(
                        'No se encontro archivo con los datos facilitados')
        return res

    @api.model
    def send_mail_to_partner(self):
        company = self.env.user.company_id
        ctx = self.env.context.copy()
        ctx['from_function'] = True
        extra_where = []
        if not company.send_mail_invoice:
            extra_where.append("invoice_out_id IS NULL")
        if not company.send_mail_credit_note:
            extra_where.append("credit_note_out_id IS NULL")
        if not company.send_mail_debit_note:
            extra_where.append("debit_note_out_id IS NULL")
        if not company.send_mail_remision:
            extra_where.append("delivery_note_id IS NULL")
        if not company.send_mail_retention:
            extra_where.append("withhold_id IS NULL")
        SQL = """SELECT id 
                    FROM sri_xml_data 
                    WHERE state = 'authorized' 
                        AND (send_mail=false OR send_mail IS NULL) %s
                    LIMIT %s""" % (extra_where and " AND " + " AND ".join(extra_where) or '', company.cron_process)
        self.env.cr.execute(SQL)
        xml_ids = map(lambda x: x[0], self.env.cr.fetchall())
        if xml_ids:
            documents_sended, documents_no_sended = self.with_context(
                ctx).browse(xml_ids).test_send_mail_partner()
            if documents_sended:
                SQL = "UPDATE sri_xml_data SET send_mail=true WHERE id IN %(xml_ids)s"
                self.env.cr.execute(SQL, {'xml_ids': tuple(documents_sended)})
            if documents_no_sended:
                SQL = "UPDATE sri_xml_data SET send_mail=false WHERE id IN %(xml_ids)s"
                self.env.cr.execute(
                    SQL, {'xml_ids': tuple(documents_no_sended)})
        return True

    def test_external_document(self):
        return True

    @api.model
    def generate_file_name(self, xml_id, file_type):
        """
        Genera el nombre del archivo, segun el tipo de documento y el tipo de archivo
        @param file_type: str, tipo de documento, se permiten(file_xml, file_signed, file_authorized)
        @return: str, el nombre del archivo segun el tipo de documento
        """
        # la estructura para el nombre seria asi
        # id del sri_xml_data
        # tipo de documento(fc->facturas, nc->Notas de credito, nd->Notas de debito, re->Retenciones, gr->Guias de remision)
        # numero del documento
        # signed o authorized, segun el file_type
        # extension xml
        document_type, document_number = "", ""
        if file_type not in ('file_xml', 'file_signed', 'file_authorized'):
            raise Warning(
                _(u"Tipo de archivo no valido, se permite signed, authorized. Por favor verifique"))
        xml_rec = self.browse()
        if self.env.context.get('portal_donwload'):
            xml_rec = self.browse(xml_id)
        else:
            xml_rec = self.browse(xml_id).sudo()
        # al nombre sumarle el _path para obtener el nombre del campo en el modelo
        field_name = file_type + "_path"
        # si el registro ya tiene path tomar ese, o crearlo cada vez??
        if field_name in self._fields and xml_rec[field_name] and not self.env.context.get('only_file', False):
            file_name = xml_rec[field_name]
        else:
            if xml_rec.invoice_out_id:
                document_type = 'fc'
                document_number = xml_rec.invoice_out_id.document_number
            elif xml_rec.credit_note_out_id:
                document_type = 'nc'
                document_number = xml_rec.credit_note_out_id.document_number
            elif xml_rec.debit_note_out_id:
                document_type = 'nd'
                document_number = xml_rec.debit_note_out_id.document_number
            elif xml_rec.delivery_note_id:
                document_type = 'gr'
                document_number = xml_rec.delivery_note_id.document_number
            elif xml_rec.withhold_id:
                document_type = 're'
                document_number = xml_rec.withhold_id.document_number
            file_name = "%s_%s_%s_%s.xml" % (
                xml_id, document_type, document_number, file_type)
        return file_name

    @api.model
    def get_file(self, xml_id, file_type):
        """Permite obtener un archivo desde el sistema de archivo
        @param file_type: str, tipo de documento, se permiten(file_xml, file_signed, file_authorized) 
        @return: El archivo en codificacion base64
        """
        # obtener el nombre del archivo
        file_name = self.generate_file_name(xml_id, file_type)
        # buscar el archivo en la ruta configurada en la compañia
        company = self.env.user.company_id
        root_path = company.path_files_electronic
        if not root_path:
            raise Warning(
                _(u"Debe configurar la ruta para guardar los documentos electronicos. Por favor verifique en la configuracion de compañia"))
        file_data = ""
        full_path = os.path.join(root_path, file_name)
        full_path = os.path.normpath(full_path)
        if os.path.isfile(full_path):
            try:
                file_save = open(full_path, "rb")
                file_data = file_save.read()
                file_save.close()
            except IOError:
                _logger.warning(_(u"No se puede leer el archivo %s, verifique permisos en la ruta %s!" % (
                    file_name, root_path)))
        else:
            raise Warning(_(u"Archivo %s no encontrado en la ruta %s") %
                          (file_name, root_path))
        return file_data

    @api.model
    def write_file(self, xml_id, file_type, file_content):
        """Permite crear un archivo firmado o autorizado
        @param file_type: str, tipo de documento, se permiten(file_xml, file_signed, file_authorized)
        @param file_content: el contenido del archivo, codificado en base64
        @return: la ruta completa del archivo creado
        """
        # obtener el nombre del archivo
        file_name = self.generate_file_name(xml_id, file_type)
        # buscar el archivo en la ruta configurada en la compañia
        company = self.env.user.company_id
        root_path = company.path_files_electronic
        if not root_path:
            raise Warning(
                _(u"Debe configurar la ruta para guardar los documentos electronicos. Por favor verifique en la configuracion de compañia"))
        full_path = os.path.join(root_path, file_name)
        full_path = os.path.normpath(full_path)
        # TODO: si el archivo ya existe, sobreescribirlo completamente
        try:
            file_save = open(full_path, "wb")
            file_save.write(file_content)
            file_save.close()
        except IOError:
            _logger.warning(_(u"No se puede escribir en el archivo %s, verifique permisos en la ruta %s!" % (
                file_name, root_path)))
        return full_path

    def get_file_to_wizard(self):
        '''
        @param file_type: str, tipo de documento, se permiten(file_xml, file_signed, file_authorized)
        '''
        wizard_model = self.env['wizard.xml.get.file']
        util_model = self.env['ecua.utils']
        xml_data = self[0]
        file_type = self.env.context.get('file_type', 'file_xml')
        file_data = self.get_file(xml_data.id, file_type)
        file_name = self.generate_file_name(xml_data.id, file_type)
        ctx = self.env.context.copy()
        ctx['active_model'] = self._name
        ctx['active_ids'] = self.ids
        ctx['active_id'] = self.ids and self.ids[0] or False
        if not file_data:
            raise Warning(_(u"No existe el fichero, no puede ser mostrado"))
        else:
            wizard_rec = wizard_model.create({'name': file_name,
                                              'file_data': base64.encodebytes(file_data),
                                              'file_type': file_type,
                                              })
            res = util_model.with_context(ctx).show_wizard(
                wizard_model._name, 'wizard_xml_get_file_form_view', _(u'Descargar Archivo'))
            res['res_id'] = wizard_rec.id
            return res

    def unlink(self):
        for xml_data in self:
            # si el documento no esta en borrador no permitir eliminar
            if xml_data.state != 'draft':
                # si esta cancelado, pero no tengo numero de autorizacion para cancelar, permitir eliminar
                if xml_data.state == 'cancel' and not xml_data.authorization_to_cancel:
                    continue
                raise Warning(
                    _(u"No puede eliminar registros a menos que esten en estado borrador"))
        res = super(sri_xml_data, self).unlink()
        return res

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        new_domain = []
        for domain in args:
            if len(domain) == 3:
                # reemplazar ilike o like por el operador =
                # mejora el rendimiento en busquedas
                if domain[0] in self.fields_size and len(domain[2]) == self.fields_size[domain[0]] and domain[1] in ('like', 'ilike'):
                    new_domain.append((domain[0], '=', domain[2]))
                    continue
                else:
                    new_domain.append(domain)
            else:
                new_domain.append(domain)
        res = super(sri_xml_data, self)._search(new_domain, offset=offset,
                                                limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)
        return res

    def get_electronic_logo_image(self):
        self.ensure_one()
        if self.shop_id.electronic_logo:
            return self.shop_id.electronic_logo
        if self.company_id.electronic_logo:
            return self.company_id.electronic_logo
        if self.company_id.logo:
            return self.company_id.logo
        return False

    def name_get(self):
        # TODO : search on name field or _res_name fields
        # and make a result [(id, name), (id, name), ...]
        res = []
        for xml_data in self:
            name = xml_data.number_document
            if xml_data.invoice_out_id:
                name = "%s" % (xml_data.invoice_out_id.display_name)
            elif xml_data.credit_note_out_id:
                name = "%s" % (xml_data.credit_note_out_id.display_name)
            elif xml_data.debit_note_out_id:
                name = "%s" % (xml_data.debit_note_out_id.display_name)
            elif xml_data.delivery_note_id:
                name = "%s" % (xml_data.delivery_note_id.display_name)
            elif xml_data.withhold_id:
                name = "%s" % (xml_data.withhold_id.display_name)

            res.append((xml_data.id, name))

        return res

    @api.model
    def send_massage_documents_no_autorization(self):

        template_mail_docs_no_autorization = self.env.ref(
            'ecua_documentos_electronicos.mail_documents_no_autorization')
        company = self.env.user.company_id
        if company.get_documents_electonic_no_autorization():
            template_mail_docs_no_autorization.send_mail(company.id)

        return True

    def action_desactive_notification_documents_no_autorization(self):
        return self.write({
            'notification_active': False,
        })

    def action_active_notification_documents_no_autorization(self):
        return self.write({
            'notification_active': True,
        })

    def get_mail_url(self):
        return self.get_share_url()


sri_xml_data()


class sri_xml_data_message_line(models.Model):

    _name = 'sri.xml.data.message.line'
    _description = 'Mensajes S.R.I.'
    _rec_name = 'message'

    xml_id = fields.Many2one('sri.xml.data', u'XML Data',
                             required=True, index=True, help=u"",)
    message_code_id = fields.Many2one(
        'sri.error.code', u'Código de Mensaje', required=True, index=True, help=u"",)
    message_type = fields.Char(u'Tipo', size=64, required=False, help=u"",)
    other_info = fields.Text(
        string=u'Información Adicional', required=False, help=u"",)
    message = fields.Text(string=u'Mensaje', required=False, help=u"",)
    create_date = fields.Datetime(
        u'Fecha de Creación', readonly=True, help=u"",)
    write_date = fields.Datetime(
        u'Ultima actualización', readonly=True, help=u"",)


sri_xml_data_message_line()


class sri_xml_data_send_try(models.Model):

    _name = 'sri.xml.data.send.try'
    _description = 'Intentos de envio a SRI'

    _rec_name = 'xml_id'

    xml_id = fields.Many2one('sri.xml.data', u'XML Data',
                             required=False, index=True, help=u"",)
    send_date = fields.Datetime(u'Send Date', help=u"",)
    response_date = fields.Datetime(u'Response Date', help=u"",)
    type_send = fields.Selection([('send', 'Enviado a Autorizar'),
                                  ('check', 'Verificar Clave de Acceso'),
                                  ], string=u'Tipo', index=True, readonly=True, default='send',
                                 help=u"",)


sri_xml_data_send_try()
