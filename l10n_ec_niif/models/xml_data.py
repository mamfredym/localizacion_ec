import pytz
import io
import os
import time
import base64
import logging
import traceback
from lxml import etree
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from datetime import datetime
from random import randint
from collections import OrderedDict

import urllib.request
from suds import WebFault
from suds.client import Client
import barcode
from barcode.writer import ImageWriter
from pprint import pformat

from odoo import models, api, fields
from odoo import tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF
import base64

from ..models import modules_mapping

_logger = logging.getLogger(__name__)

DOCUMENT_TYPES = {
    'out_invoice': '01',
    'out_refund': '04',
    'debit_note_out': '05',
    'delivery_note': '06',
    'withhold_purchase': '07',
    'liquidation': '03',
}

DOCUMENT_MODELS = {
    'out_invoice': 'account.move',
    'out_refund': 'account.move',
    'debit_note_out': 'account.move',
    'liquidation': 'account.move',
    'delivery_note': 'l10n_ec.delivery.note',
    'withhold_purchase': 'l10n_ec.withhold',
}

DOCUMENT_XSD_FILES = {
    'out_invoice': 'Factura_V1.0.0.xsd',
    'liquidation': 'Liquidacion_Compra_V_1_1_0.xsd',
    'out_refund': 'notaCredito_1.1.0.xsd',
    'debit_note_out': 'notaDebito_1.1.1.xsd',
    'delivery_note': 'guiaRemision_1.1.0.xsd',
    'withhold_purchase': 'comprobanteRetencion_1.1.1.xsd',
    'lote_masivo': 'loteMasivo_1.0.0.xsd',
}

DOCUMENT_FIELDS = {
    'out_invoice': 'l10n_latam_document_number',
    'liquidation': 'l10n_latam_document_number',
    'out_refund': 'l10n_latam_document_number',
    'debit_note_out': 'l10n_latam_document_number',
    'delivery_note': 'document_number',
    'withhold_purchase': 'document_number',
}

DOCUMENT_FIELDS_DATE = {
    'out_invoice': 'invoice_date',
    'out_refund': 'invoice_date',
    'debit_note_out': 'invoice_date',
    'liquidation': 'invoice_date',
    'delivery_note': 'transfer_date',
    'withhold_purchase': 'issue_date',
}

FIELDS_NAME = {
    'out_invoice': 'invoice_out_id',
    'out_refund': 'credit_note_out_id',
    'debit_note_out': 'debit_note_out_id',
    'liquidation': 'liquidation_id',
    'delivery_note': 'delivery_note_id',
    'withhold_purchase': 'withhold_id',
}

XML_FIELDS_NAME = {
    'simple_xml': 'xml_file',
    'signed_xml': 'xml_signed_file',
    'authorized_xml': 'xml_authorized_file',
}

FIELD_FOR_SEND_MAIL_DOCUMENT = {
    'out_invoice': 'send_mail_invoice',
    'out_refund': 'send_mail_credit_note',
    'debit_note_out': 'send_mail_debit_note',
    'liquidation': 'send_mail_liquidation',
    'delivery_note': 'send_mail_remision',
    'withhold_purchase': 'send_mail_retention',
}


class SriXmlData(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _name = 'sri.xml.data'
    _description = 'SRI XML Electronic'
    _rec_name = 'number_document'

    fields_size = {
        'xml_key': 49,
        'xml_authorization': 49,
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

    @api.depends('invoice_out_id', 'credit_note_out_id', 'debit_note_out_id', 'withhold_id', 'delivery_note_id',
                 'liquidation_id',
                 'invoice_out_id.invoice_date', 'credit_note_out_id.invoice_date', 'debit_note_out_id.invoice_date',
                 'liquidation_id.invoice_date',
                 'withhold_id.issue_date')
    def _compute_document_datas(self):
        for xml_data in self:
            number = 'SN'
            date_emision_document = False
            point_emission = self.env['l10n_ec.point.of.emission']
            if xml_data.invoice_out_id:
                number = 'FV: %s' % xml_data.with_context(only_number=True).invoice_out_id.display_name
                date_emision_document = xml_data.invoice_out_id.invoice_date
                point_emission = xml_data.invoice_out_id.l10n_ec_point_of_emission_id
            elif xml_data.credit_note_out_id:
                number = 'NCC: %s' % xml_data.with_context(only_number=True).credit_note_out_id.display_name
                date_emision_document = xml_data.credit_note_out_id.invoice_date
                point_emission = xml_data.credit_note_out_id.l10n_ec_point_of_emission_id
            elif xml_data.debit_note_out_id:
                number = 'NDC: %s' % xml_data.with_context(only_number=True).debit_note_out_id.display_name
                date_emision_document = xml_data.debit_note_out_id.invoice_date
                point_emission = xml_data.debit_note_out_id.l10n_ec_point_of_emission_id
            elif xml_data.withhold_id:
                number = 'RET: %s' % xml_data.withhold_id.display_name
                date_emision_document = xml_data.withhold_id.issue_date
                point_emission = xml_data.withhold_id.point_of_emission_id
            elif xml_data.delivery_note_id:
                number = 'GR: %s' % xml_data.delivery_note_id.display_name
                date_emision_document = xml_data.delivery_note_id.transfer_date
                point_emission = xml_data.delivery_note_id.l10n_ec_point_of_emission_id
            elif xml_data.liquidation_id:
                number = 'LIQ: %s' % xml_data.with_context(only_number=True).liquidation_id.display_name
                date_emision_document = xml_data.liquidation_id.invoice_date
                point_emission = xml_data.liquidation_id.l10n_ec_point_of_emission_id
            xml_data.number_document = number
            xml_data.date_emision_document = date_emision_document
            xml_data.l10n_ec_point_of_emission_id = point_emission

    number_document = fields.Char('Document Number', compute='_compute_document_datas', store=True, index=True)
    date_emision_document = fields.Date(u'Fecha de emision', compute='_compute_document_datas', store=True, index=True)
    l10n_ec_point_of_emission_id = fields.Many2one('l10n_ec.point.of.emission', string='Punto de Emisión',
        compute='_compute_document_datas', store=True, index=True)
    agency_id = fields.Many2one('l10n_ec.agency', string='Agencia', related="l10n_ec_point_of_emission_id.agency_id", store=True)
    file_xml_path = fields.Char('Ruta de Archivo XML')
    file_signed_path = fields.Char('Ruta de Archivo Firmado')
    file_authorized_path = fields.Char('Ruta de Archivo Autorizado')
    xml_file_version = fields.Char('Version XML')
    xml_key = fields.Char('Clave de Acceso', size=49, readonly=True, index=True)
    xml_authorization = fields.Char('Autorización SRI', size=49, readonly=True, index=True)
    description = fields.Char('Description')
    invoice_out_id = fields.Many2one('account.move', 'Factura', index=True, auto_join=True)
    credit_note_out_id = fields.Many2one('account.move', 'Nota de Crédito', index=True, auto_join=True)
    debit_note_out_id = fields.Many2one('account.move', 'Nota de Débito', index=True, auto_join=True)
    liquidation_id = fields.Many2one('account.move', 'Liquidacion de compras', index=True, auto_join=True)
    withhold_id = fields.Many2one('l10n_ec.withhold', 'Retención', index=True, auto_join=True)
    delivery_note_id = fields.Many2one('l10n_ec.delivery.note', 'Guia de Remision', index=True, auto_join=True)
    company_id = fields.Many2one('res.company', string='Compañía')
    partner_id = fields.Many2one('res.partner', 'Cliente', index=True, auto_join=True)
    create_uid = fields.Many2one('res.users', 'Creado por', readonly=True)
    create_date = fields.Datetime('Fecha de Creación', readonly=True)
    signed_date = fields.Datetime('Fecha de Firma', readonly=True, index=True)
    send_date = fields.Datetime('Fecha de Envío', readonly=True)
    response_date = fields.Datetime('Fecha de Respuesta', readonly=True)
    authorization_date = fields.Datetime('Fecha de Autorización', readonly=True, index=True)
    notification_active = fields.Boolean(string='Notificación de Documentos Electrónicos no Autorizados?', default=True,
        help="Esto permite activar o desactivar las notificaciones del presente documento")
    xml_type = fields.Selection([
        ('individual', 'Individual'),
        ('grouped', 'Agrupado / Lote Masivo'),
    ], string='Tipo', index=True, readonly=True, default='individual')
    type_conection_sri = fields.Selection([
        ('online', 'On-Line'),
        ('offline', 'Off-Line'),
    ], string=u'Tipo de conexion con SRI', default='offline')
    state = fields.Selection([
        ('draft', 'Creado'),
        # emitido en contingencia no es igual a esperar autorizacion(clave 70)
        ('contingency', 'Emitido en contingencia'),
        ('signed', 'Firmado'),
        # Emitido x Contingencia, en espera de autorizacion
        ('waiting', 'En Espera de Autorización'),
        ('authorized', 'Autorizado'),
        ('returned', 'Devuelta'),
        ('rejected', 'No Autorizado'),
        ('cancel', 'Cancelado'),
    ], string='Estado', index=True, readonly=True, default='draft')
    type_environment = fields.Selection([
        ('test', 'Pruebas'),
        ('production', 'Producción'),
    ], string='Tipo de Ambiente', index=True, readonly=True)
    type_emision = fields.Selection([
        ('normal', 'Normal'),
        ('contingency', 'Contingencia'),
    ], string='Tipo de Emisión', index=True, readonly=True)
    last_error_id = fields.Many2one('sri.error.code', 'Ultimo Mensaje de error', readonly=True, index=True)
    sri_message_ids = fields.One2many('sri.xml.data.message.line', 'xml_id', 'Mensajes Informativos', auto_join=True)
    try_ids = fields.One2many('sri.xml.data.send.try', 'xml_id', 'Send Logs', auto_join=True)
    # campo para enviar los mail a los clientes por lotes, u mejorar el proceso de autorizacion
    send_mail = fields.Boolean('Mail enviado?')
    # cuando el documento sea externo,
    # los campos funcionales no se calcularan en ese instante
    # y tampoco se hace el envio al sri en ese instante
    # una tarea cron se encargara de eso
    # este campo es para no calcular los datos cada vez que se ejecute la tarea cron, solo la primera vez
    external_document = fields.Boolean('Documento Externo?', readonly=True)
    process_now = fields.Boolean('Procesar Documento Externo?', default=True, readonly=True)
    fields_function_calculate = fields.Boolean('Campos funcionales calculados?')
    external_data = fields.Text(string='Informacion Externa importada', readonly=True)
    # campo para el numero de autorizacion cuando se cancelan documentos electronicos
    authorization_to_cancel = fields.Char('Autorización para cancelar', size=64, readonly=True)
    cancel_date = fields.Datetime('Fecha de cancelación', readonly=True)
    cancel_user_id = fields.Many2one('res.users', 'Usuario que canceló', readonly=True)

    _sql_constraints = [
        ('invoice_out_id_uniq', 'unique (invoice_out_id)', 'Ya existe una factura con el mismo numero!'),
        ('credit_note_out_id_uniq', 'unique (credit_note_out_id)', 'Ya existe una Nota de credito con el mismo numero!'),
        ('debit_note_out_id_uniq', 'unique (debit_note_out_id)', 'Ya existe una Nota de debito con el mismo numero!'),
        ('liquidation_id_uniq', 'unique (liquidation_id)', 'Ya existe una Liquidacion de compras con el mismo numero!'),
        ('withhold_id_uniq', 'unique (withhold_id)', 'Ya existe una Retencion con el mismo numero!'),
        ('delivery_note_id_uniq', 'unique (delivery_note_id)', 'Ya existe una Guia de remision con el mismo numero!'),
    ]

    @api.model
    def get_current_wsClient(self, conection_type):
        # Debido a que el servidor me esta rechazando las conexiones contantemente, es necesario que se cree una sola instancia
        # Para conexion y asi evitar un reinicio constante de la comunicacion
        wsClient = None
        company = self.env.user.company_id
        try:
            if conection_type == 'ws_receipt_test':
                if self._ws_receipt_test and self._ws_receipt_test.wsdl.url == company.ws_receipt_test:
                    wsClient = self._ws_receipt_test
                else:
                    wsClient = Client(company.ws_receipt_test, timeout=company.ws_timeout)
                    self._ws_receipt_test = wsClient
            if conection_type == 'ws_auth_test':
                if self._ws_auth_test and self._ws_auth_test.wsdl.url == company.ws_auth_test:
                    wsClient = self._ws_auth_test
                else:
                    wsClient = Client(company.ws_auth_test, timeout=company.ws_timeout)
                    self._ws_auth_test = wsClient
            if conection_type == 'ws_receipt_production':
                if self._ws_receipt_production and self._ws_receipt_production.wsdl.url == company.ws_receipt_production:
                    wsClient = self._ws_receipt_production
                else:
                    wsClient = Client(ws_receipt_production,
                                      timeout=company.ws_timeout)
                    self._ws_receipt_production = wsClient
            if conection_type == 'ws_auth_production':
                if self._ws_auth_production and self._ws_auth_production.wsdl.url == company.ws_auth_production:
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

    def get_current_document(self):
        self.ensure_one()
        document = self.invoice_out_id
        if not document and self.credit_note_out_id:
            document = self.credit_note_out_id
        if not document and self.debit_note_out_id:
            document = self.debit_note_out_id
        if not document and self.liquidation_id:
            document = self.liquidation_id
        if not document and self.withhold_id:
            document = self.withhold_id
        if not document and self.delivery_note_id:
            document = self.delivery_note_id
        return document

    @api.model
    def get_sequence(self, l10n_ec_point_of_emission_id, number):
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
            list_characters = [
                ('á', 'a'), ('à', 'a'), ('ä', 'a'), ('â', 'a'), ('Á', 'A'), ('À', 'A'), ('Ä', 'A'), ('Â', 'A'),
                ('é', 'e'), ('è', 'e'), ('ë', 'e'), ('ê', 'e'), ('É', 'E'), ('È', 'E'), ('Ë', 'E'), ('Ê', 'E'),
                ('í', 'i'), ('ì', 'i'), ('ï', 'i'), ('î', 'i'), ('Í', 'I'), ('Ì', 'I'), ('Ï', 'I'), ('Î', 'I'),
                ('ó', 'o'), ('ò', 'o'), ('ö', 'o'), ('ô', 'o'), ('Ó', 'O'), ('Ò', 'O'), ('Ö', 'O'), ('Ô', 'O'),
                ('ú', 'u'), ('ù', 'u'), ('ü', 'u'), ('û', 'u'), ('Ú', 'U'), ('Ù', 'U'), ('Ü', 'U'), ('Û', 'U'),
                ('ñ', 'n'), ('Ñ', 'N'), ('/', '-'), ('&', 'Y'), ('º', ''), ('´', '')
            ]
        for character in list_characters:
            string_to_reeplace = string_to_reeplace.replace(character[0], character[1])
        SPACE = ' '
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
            raise UserError(
                _("Debe configurar la direccion del webservice de pruebas del SRI"))
        if not company.ws_receipt_production:
            raise UserError(
                _("Debe configurar la direccion del webservice de produccion del SRI"))
        # Durante pruebas solo enviar 1
        res = '1'
        # CHECKME: se debe asumir que hay conexion en la creacion de los datos
        if 'sign_now' in self.env.context and not self.env.context.get('sign_now', False):
            return res
        if environment == '1':
            try:
                code = urllib.request.urlopen(company.ws_receipt_test).getcode()
                _logger.info("Conection Succesful with %s. Code %s",
                             company.ws_receipt_test, code)
                if code == 200:
                    res = '1'
                else:
                    res = '2'
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning(
                    "Error in Conection with %s, set in contingency mode. ERROR: %s", company.ws_receipt_test, error)
                # no pasar que es contingencia
                res = '1'
        elif environment == '2':
            try:
                code = urllib.request.urlopen(
                    company.ws_receipt_production).getcode()
                _logger.info("Conection Succesful with %s. Code %s",
                             company.ws_receipt_production, code)
                if code == 200:
                    res = '1'
                else:
                    res = '2'
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning("Error in Conection with %s, set in contingency mode. ERROR: %s",
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
        elif invoice_type == 'liquidation' and company.electronic_liquidation:
            document_active = True
        elif invoice_type == 'lote_masivo' and company.electronic_batch:
            document_active = True
        return document_active

    @api.model
    def is_enviroment_production(self, invoice_type, printer_emission):
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
        if printer_emission.type_emission != 'electronic':
            return False
        enviroment = self._get_environment(company)
        # verificar si el tipo de documento esta configurado como autorizado para emitir
        # antes de verificar si el webservice responde,
        # para no hacer peticion al webservice en vano, si el documento no esta autorizado a emitir
        if enviroment == '2' and self._is_document_authorized(invoice_type):
            res = True
        return res

    @api.model
    def get_check_digit(self, key):
        """Devuelve el digito verificador por el metodo del modulo 11
        :param key: Llave a Verificar
        :rtype: clave para adjuntar al xml a ser firmado
        """
        mult = 1
        sum = 0
        # Paso 1, 2, 3
        for i in reversed(list(range(len(key)))):
            mult += 1
            if mult == 8:
                mult = 2
            sum += int(key[i]) * mult
        # Paso 4 y 5
        check_digit = 11 - (sum % 11)
        if check_digit == 11:
            check_digit = 0
        if check_digit == 10:
            check_digit = 1
        return check_digit

    @api.model
    def get_single_key(self, type_voucher, environment, printer_point_id, sequence, emission, xml_type='individual',
                       date_document=None):
        """Devuelve la clave para archivo xml a enviar a firmar en comprobantes unicos
        :param type_voucher: Puede ser los siguientes tipos :
            01 : Factura
            04 : Nota de Credito
            05 : Nota de Debito
            06 : Guia de Remision
            07 : Comprobante de Retencion
        :param environment: Puede ser los siguientes ambientes :
            1 : Pruebas
            2 : Produccion
        :param printer_point_id: Punto de Emision del Documento, con esto se obtendra la serie del documento p.e. 001001
        :param sequence: El secuencial del Documento debe ser tipo numerico
        :param emission: El tipo de emision puede ser:
            1 : Emision Normal
            2 : Emision por Indisponibilidad del Sistema
        :param xml_type: El tipo de xml:
            1 : individual Individual un solo documento
            2 : grouped Agrupado varios xml mas
        :rtype: clave para adjuntar al xml a ser firmado
        """
        printer_model = self.env['l10n_ec.point.of.emission']
        company = self.env.user.company_id
        printer = printer_model.browse(printer_point_id)
        if not date_document:
            date_document = fields.Date.context_today(self)
        now_date = date_document.strftime('%d%m%Y')
        serie = printer.agency_id.number + printer.number
        sequencial = str(sequence).rjust(9, '0')
        prenumber = '0'
        if xml_type == 'individual' and emission == '1':
            code_numeric = randint(1, 99999999)
            code_numeric = str(code_numeric).rjust(8, '0')
            prenumber = now_date + type_voucher + company.partner_id.vat + environment + serie + sequencial + code_numeric + emission
        check_digit = '%s' % self.get_check_digit(prenumber)
        key_value = prenumber + check_digit
        return key_value

    @api.model
    def generate_info_tributaria(self, xml_id, node, document_type, environment, emission, company, printer_id,
                                 sequence, date_document):
        """Asigna al nodo raiz la informacion tributaria que es comun en todos los documentos, asigna clave interna
        al documento para ser firmado posteriormente
        :param xml_id: identification xml_data
        :param node: tipo Element
        :param document_type: Puede ser los tipos :
            01 : Factura
            03 : Liquidacion de Compras
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
        printer_model = self.env['l10n_ec.point.of.emission']
        printer = printer_model.browse(printer_id)
        infoTributaria = SubElement(node, "infoTributaria")
        SubElement(infoTributaria, "ambiente").text = environment
        # emision para 1 pruebas, 2 produccion, 3 contingencia
        # pero webservice solo acepta 1 emision normal, 2 emision por contingencia
        SubElement(infoTributaria, "tipoEmision").text = emission
        xml_data = self.browse(xml_id)
        razonSocial = 'PRUEBAS SERVICIO DE RENTAS INTERNAS'
        nombreComercial = 'PRUEBAS SERVICIO DE RENTAS INTERNAS'
        if environment == '2':
            razonSocial = self._clean_str(company.partner_id.name)
            nombreComercial = self._clean_str(company.partner_id.business_name or razonSocial)
        SubElement(infoTributaria, "razonSocial").text = razonSocial
        SubElement(infoTributaria, "nombreComercial").text = nombreComercial
        SubElement(infoTributaria, "ruc").text = company.partner_id.vat
        clave_acceso = xml_data.xml_key
        if not clave_acceso:
            clave_acceso = self.get_single_key(document_type, environment, printer_id, sequence, emission,
                                               xml_data.xml_type, date_document)
        SubElement(infoTributaria, "claveAcceso").text = clave_acceso
        SubElement(infoTributaria, "codDoc").text = document_type
        SubElement(infoTributaria, "estab").text = printer.agency_id.number
        SubElement(infoTributaria, "ptoEmi").text = printer.number
        SubElement(infoTributaria, "secuencial").text = str(sequence).rjust(9, '0')
        # Debe ser la direccion matriz
        company_address = company.partner_id.get_direccion_matriz(printer)
        SubElement(infoTributaria, "dirMatriz").text = self._clean_str(company_address or '')
        return clave_acceso, node

    def check_xsd(self, xml_string, xsd_file_path):
        try:
            xsd_file = tools.file_open(xsd_file_path)
            xmlschema_doc = etree.parse(xsd_file)
            xmlschema = etree.XMLSchema(xmlschema_doc)
            xml_doc = etree.fromstring(xml_string)
            result = xmlschema.validate(xml_doc)
            if not result:
                xmlschema.assert_(xml_doc)
            return result
        except AssertionError as e:
            if self.env.context.get('call_from_cron'):
                _logger.error('XML Mal Creado, faltan datos, verifique clave de acceso: %s, Detalle de error: %s',
                              self.xml_key, tools.ustr(e))
            else:
                raise UserError('XML Mal Creado, faltan datos, verifique: \n%s' % tools.ustr(e))
        return True

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
        util_model = self.env['l10n_ec.utils']
        company = self.env.user.company_id
        sign_now = self.env.context.get('sign_now', True)
        xml_data = self.browse(xml_id)
        document_type = modules_mapping.get_document_type(invoice_type)
        field_name = modules_mapping.get_field_name(document_type)
        model_name = modules_mapping.get_model_name(document_type)
        doc_model = self.env[model_name]
        environment = self._get_environment(company)
        xml_version = company[document_type + '_version_xml_id']
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
        send_mail_for_document = FIELD_FOR_SEND_MAIL_DOCUMENT[invoice_type] and getattr(company,
                                                                                        FIELD_FOR_SEND_MAIL_DOCUMENT[
                                                                                            invoice_type],
                                                                                        False) or False
        printer_id = document.l10n_ec_point_of_emission_id.id
        sequence = ''
        if xml_data.xml_type == 'individual':
            sequence = self.get_sequence(printer_id, document[field_name])
        root = Element(xml_version.xml_header_name, id="comprobante", version=xml_version.version_file)
        clave_acceso, root = self.generate_info_tributaria(xml_id, root, DOCUMENT_TYPES.get(invoice_type),
                                                           environment, emission, company, printer_id, sequence,
                                                           document[DOCUMENT_FIELDS_DATE.get(invoice_type)])
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
        xml_data.write({
            'type_environment': type_environment,
            'type_emision': type_emision,
            'state': state,
            'xml_key': clave_acceso,
            'partner_id': partner_id and partner_id.id or False,
        })
        # escribir en los objetos relacionados, la clave de acceso y el xml_data para pasar la relacion
        document.write({
            'xml_key': clave_acceso,
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
            # liquidacion de compras
            elif invoice_type == 'liquidation':
                doc_model.get_info_liquidation(document_id, root)
            elif invoice_type == 'withhold_purchase':
                doc_model.get_info_withhold(document_id, root)
            elif invoice_type == 'delivery_note':
                doc_model.get_info_delivery_note(document_id, root)
        # Se identa con propositos de revision, no debe ser asi al enviar el documento
        util_model.indent(root)
        bytes_data = tostring(root, encoding="UTF-8")
        string_data = bytes_data.decode()
        # xml_data.check_xsd(string_data, xml_version.file_path)
        binary_data = base64.encodebytes(bytes_data)
        return string_data, binary_data

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
                _logger.warning("Clave 70, en espera de autorizacion. %s %s", message.get('mensaje', ''),
                                message.get('informacionAdicional', ''))
                xml_rec.write({'state': 'waiting'})
                raise_error = False
            error_recs = error_model.search([('code', '=', message.get('identificador'))])
            if error_recs:
                last_error_rec = error_recs[0]
            # el mensaje 60 no agregarlo, es informativo y no debe lanzar excepcion por ese error
            if message.get('identificador') and message.get('identificador') not in ('60', 60):
                messages_error.append("%s. %s" % (message.get('mensaje'), message.get('informacionAdicional')))
            vals_messages = {
                'xml_id': xml_id,
                'message_code_id': last_error_rec.id,
                'message_type': message.get('tipo'),
                'other_info': message.get('informacionAdicional'),
                'message': message.get('mensaje'),
            }
            for msj in xml_rec.sri_message_ids:
                # si ya existe un mensaje con el mismo codigo
                # y el texto es el mismo, modificar ese registro
                if msj.message_type in ('ERROR', 'ERROR DE SERVIDOR') and last_error_rec:
                    last_error_id = last_error_rec.id
                if msj.message_code_id and last_error_rec:
                    if msj.message_code_id.id == last_error_rec.id and (
                            msj.message == message.get('mensaje') or msj.other_info == message.get('other_info')):
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
                try_rec = try_model.create({
                    'xml_id': xml_id,
                    'send_date': time.strftime(DTF),
                    'type_send': 'check',
                })
                responseAuth = client_ws_auth.service.autorizacionComprobante(claveAccesoComprobante=xml_rec.xml_key)
                try_rec.write({'response_date': time.strftime(DTF)})
                ok, msgs = self._process_response_autorization(
                    xml_id, responseAuth)
                if ok:
                    response = {'estado': 'RECIBIDA'}
                    # Si ya fue recibida y autorizada, no tengo que volver a enviarla
                    send = False
            if self.env.context.get('no_send'):
                send = False
            if send:
                try_rec = try_model.create({
                    'xml_id': xml_id,
                    'send_date': time.strftime(DTF),
                    'type_send': 'send',
                })
                response = client_ws.service.validarComprobante(
                    xml=base64.encodebytes(self.get_file(xml_id, xml_field).encode()).decode())
                try_model.write({'response_date': time.strftime(DTF)})
                _logger.info("Send file succesful, claveAcceso %s. %s", xml_rec.xml_key,
                             str(response.estado) if hasattr(response, 'estado') else 'SIN RESPUESTA')
            xml_rec.write({'response_date': time.strftime(DTF)})
        except WebFault as ex:
            error = self._clean_str(tools.ustr(ex))
            xml_rec.write({'state': 'waiting'})
            ok = False
            _logger.info("Error de servidor. %s", error)
            messajes = [{
                'identificador': '50',
                'informacionAdicional': 'Cuando ocurre un error inesperado en el servidor.',
                'mensaje': 'Error Interno General del servidor',
                'tipo': 'ERROR DE SERVIDOR',
            }]
            self._create_messaje_response(xml_id, messajes, ok, False)
        except Exception as e:
            error = self._clean_str(tools.ustr(e))
            _logger.info("can\'t validate document in %s, claveAcceso %s. ERROR: %s", str(client_ws), xml_rec.xml_key,
                         error)
            tr = self._clean_str(tools.ustr(traceback.format_exc()))
            _logger.info("can\'t validate document in %s, claveAcceso %s. TRACEBACK: %s", str(client_ws),
                         xml_rec.xml_key, tr)
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
                comprobantes = hasattr(response.comprobantes, 'comprobante') and response.comprobantes.comprobante or []
                for comprobante in comprobantes:
                    for msj in comprobante.mensajes.mensaje:
                        msj_res.append({
                            'identificador': msj.identificador if hasattr(msj, 'identificador') else '',
                            'informacionAdicional': msj.informacionAdicional if hasattr(msj,
                                                                                        'informacionAdicional') else '',
                            'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else '',
                            'tipo': msj.tipo if hasattr(msj, 'tipo') else '',
                        })
                        # si el mensaje es error, se debe mostrar el msj al usuario
                        if hasattr(msj, 'tipo') and msj.tipo == 'ERROR':
                            error = True
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.info("can\'t validate document, claveAcceso %s. ERROR: %s", xml_rec.xml_key, error)
                tr = self._clean_str(tools.ustr(traceback.format_exc()))
                _logger.info("can\'t validate document, claveAcceso %s. TRACEBACK: %s", xml_rec.xml_key, tr)
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
            _logger.info("Error de servidor: %s", error)
            messajes = [{
                'identificador': '50',
                'informacionAdicional': 'Cuando ocurre un error inesperado en el servidor.',
                'mensaje': 'Error Interno General del servidor',
                'tipo': 'ERROR DE SERVIDOR',
            }]
            self._create_messaje_response(xml_id, messajes, False, False)
        except Exception as e:
            response = False
            xml_rec.write({'state': 'waiting'})
            # FIX: pasar a unicode para evitar problemas
            error = self._clean_str(tools.ustr(e))
            _logger.warning("Error send xml to server %s. ERROR: %s", client_ws, error)
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
            _logger.warning("Data dump: %s", data_srt)

        if not response:
            # si no tengo respuesta, dejar el documento en espera de autorizacion, para que la tarea cron se encargue de procesarlo y no quede firmado el documento
            _logger.warning(
                "Authorization response error, No response get. Documento en espera de autorizacion")
            xml_rec.write({'state': 'waiting'})
            return ok, msj_res
        if isinstance(response, object) and not hasattr(response, 'autorizaciones'):
            # si no tengo respuesta, dejar el documento en espera de autorizacion, para que la tarea cron se encargue de procesarlo y no quede firmado el documento
            _logger.warning(
                "Authorization response error, No Autorizacion in response. Documento en espera de autorizacion")
            xml_rec.write({'state': 'waiting'})
            return ok, msj_res
        # a veces el SRI devulve varias autorizaciones, unas como no autorizadas
        # pero otra si autorizada, si pasa eso, tomar la que fue autorizada
        # las demas ignorarlas
        autorizacion_list = []
        list_aux = []
        authorization_date = False
        if isinstance(response.autorizaciones, str):
            _logger.warning("Authorization data error, reponse message is not correct. %s",
                            str(response.autorizaciones))
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
                # tomar la fecha de autorizacion que envia el SRI
                authorization_date = doc.fechaAutorizacion if hasattr(doc, 'fechaAutorizacion') else False
                # si no es una fecha valida, tomar la fecha actual del sistema
                if not isinstance(authorization_date, datetime):
                    authorization_date = datetime.now()
                if authorization_date.tzinfo:
                    authorization_date = authorization_date.astimezone(pytz.UTC)
                _logger.info(u"Authorization succesful, claveAcceso %s. Autohrization: %s. Fecha de autorizacion: %s",
                             xml_rec.xml_key, str(numeroAutorizacion), authorization_date)
                vals['xml_authorization'] = str(numeroAutorizacion)
                vals['authorization_date'] = authorization_date.strftime(DTF)
                vals['state'] = 'authorized'
                # escribir en los objetos relacionados, la autorizacion y fecha de autorizacion
                document = xml_rec.get_current_document()
                if document:
                    document.action_update_authorization_data(numeroAutorizacion, authorization_date)
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
                            msj_res.append({
                                'identificador': msj.identificador if hasattr(msj, 'identificador') else '',
                                'informacionAdicional': msj.informacionAdicional if hasattr(msj,
                                                                                            'informacionAdicional') else '',
                                'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else '',
                                'tipo': msj.tipo if hasattr(msj, 'tipo') else '',
                            })
                    else:
                        for msj in doc.mensajes:
                            msj_res.append({
                                'identificador': msj.identificador if hasattr(msj, 'identificador') else '',
                                'informacionAdicional': msj.informacionAdicional if hasattr(msj,
                                                                                            'informacionAdicional') else '',
                                'mensaje': msj.mensaje if hasattr(msj, 'mensaje') else '',
                                'tipo': msj.tipo if hasattr(msj, 'tipo') else '',
                            })
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                _logger.warning("Can\'t process messages %s. ERROR: %s", doc.mensajes, error)
                print((traceback.format_exc()))
        return ok, msj_res

    def create_file_authorized(self):
        for xml_data in self:
            # el xml debe estar autorizado, tener fecha de autorizacion
            # si tengo xml firmado, a ese anexarle la autorizacion
            if xml_data.state == 'authorized' and xml_data.xml_authorization and xml_data.file_signed_path:
                tree = ET.parse(self.generate_file_name(xml_data.id, 'file_signed'))
                root = Element("RespuestaAutorizacion")
                authorizacion_ele = Element('estado')
                authorizacion_ele.text = "AUTORIZADO"
                root.append(authorizacion_ele)
                # anexar la fecha y numero de autorizacion
                authorizacion_ele = Element('numeroAutorizacion')
                authorizacion_ele.text = xml_data.xml_authorization
                root.append(authorizacion_ele)
                authorizacion_ele = Element('fechaAutorizacion')
                authorizacion_ele.text = fields.Datetime.context_timestamp(xml_data,
                                                                           xml_data.authorization_date).strftime(DTF)
                root.append(authorizacion_ele)
                authorizacion_ele = Element('ambiente')
                authorizacion_ele.text = "PRODUCCION" if xml_data.type_environment == 'production' else 'PRUEBAS'
                root.append(authorizacion_ele)
                # agregar el resto del xml
                root.append(tree.getroot())
                xml_authorized = tostring(root).decode()
                file_authorized_path = self.write_file(xml_data.id, 'file_authorized', xml_authorized)
                xml_data.write({'file_authorized_path': file_authorized_path, })
                # crear el adjunto
                document = xml_data.get_current_document()
                document.create_attachments()
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
                response = self._send_xml_data_to_valid(xml_id, xml_field, receipt_client, auth_client)
                res_ws_valid, msj, raise_error, previous_authorized = self._process_response_check(xml_id, response)
                message_data.extend(msj)
                # si no hay respuesta, el webservice no esta respondiendo, la tarea cron se debe encargar de este proceso
                # solo cuando no hay errores, si hay errores el webservice esta respondiendo y debo mostrar los msj al usuario
                if not res_ws_valid and not raise_error:
                    send_again = True
                elif res_ws_valid and not previous_authorized:
                    response_auth = self._send_xml_data_to_autorice(xml_id, xml_field, auth_client)
                    # si el sri no me respondio o no es la respuesta que esperaba
                    # verificar si quedo en procesamiento antes de volver a autorizar
                    if not response_auth or isinstance(response_auth.autorizaciones, str):
                        response_check = self._send_xml_data_to_valid(xml_id, xml_field, receipt_client, auth_client)
                        res_ws_valid, msj, raise_error, previous_authorized = self._process_response_check(xml_id,
                                                                                                           response_check)
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
                    "Error send xml to server %s. ERROR: %s", ws_receipt, error)
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
            messages_error.insert(0, "No se pudo autorizar, se detalla errores recibidos")
            raise UserError("\n".join(messages_error))
        return authorized

    @api.model
    def make_barcode(self, number):
        # El tipo puede ser A, B, C
        # Se usa el identificador de aplicacion 99 debido a que es una aplicacion interna
        code = barcode.Code128(str(number), writer=ImageWriter())
        fp = io.BytesIO()
        code.write(fp, text="")
        fp.seek(0)
        data = fp.read()
        fp.close()
        return base64.encodebytes(data)

    def _get_messages_before_sent_sri(self, res_document, document_type):
        '''
        Validar ciertos campos y devolver una lista de mensajes si no es cumple alguna validacion de datos
        '''
        return []

    def text_write_binary(self):
        xml_to_notify = {}
        xml_to_sign = self.browse()
        for xml_rec in self:
            res_document = xml_rec.get_current_document()
            if not res_document:
                continue
            # procesar los modelos que son de account.invoice(facturas, NC, ND)
            invoice_type = ""
            if res_document._name == 'account.move':
                invoice_type = res_document.get_invoice_type(res_document.type, res_document.l10n_ec_debit_note,
                                                             res_document.l10n_ec_liquidation)
            elif res_document._name == 'account.retention':
                invoice_type = 'withhold_purchase'
            elif res_document._name == 'stock.picking':
                invoice_type = 'delivery_note'
            if res_document and invoice_type:
                if self.env.context.get('call_from_cron', False):
                    message_list = xml_rec._get_messages_before_sent_sri(res_document, invoice_type)
                    if message_list:
                        xml_to_notify[xml_rec] = message_list
                        continue
                xml_to_sign |= xml_rec
                string_data, binary_data = self.generate_xml_file(xml_rec.id, res_document.id, invoice_type,
                                                                  'individual')
                file_xml_path = self.write_file(xml_rec.id, 'file_xml', string_data)
                xml_rec.write({'file_xml_path': file_xml_path})
        return xml_to_sign, xml_to_notify

    def test_sing_xml_file(self):
        def _print_error(er):
            if xml_rec.external_document:
                error = self._clean_str(tools.ustr(er))
                _logger.warning("Error sing xml data ID: %s. ERROR: %s", xml_rec.id, error)
            else:
                raise

        company = self.env.user.company_id
        if tools.config.get('no_electronic_documents') and company.type_environment == 'production':
            return True
        #        ws_signer = Client(company.ws_signer)
        for xml_rec in self:
            vals = {}
            try:
                if not company.key_type_id:
                    raise UserError(
                        "Es obligatorio seleccionar el tipo de llave o archivo de cifrado usa para la firma de los documentos electrónicos, verificar la configuración de la compañia")
                if xml_rec.file_xml_path:
                    xml_string_data = self.get_file(xml_rec.id, 'file_xml')
                    xml_signed = company.key_type_id.action_sign(xml_string_data)
                    if not xml_signed:
                        raise UserError("No se pudo firmar el documento, " \
                                        "por favor verifique que la configuracion de firma electronica este correcta")
                    file_signed_path = self.write_file(xml_rec.id, 'file_signed', xml_signed)
                    vals = {
                        'file_signed_path': file_signed_path,
                        'signed_date': time.strftime(DTF),
                    }
                # si esta en contingencia, no cambiar de estado, para que la tarea cron sea el que procese estos registros
                vals['state'] = 'signed'
                if vals:
                    xml_rec.write(vals)
            except ValidationError as ve:
                _print_error(ve)
            except UserError as w:
                _print_error(w)
            except Exception:
                raise
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
        partner_mail_model = self.env['res.partner.mail']
        invoice_type = ''
        documents_sended = {}
        documents_no_sended = {}
        company = self.env.user.company_id
        counter = 1
        total = len(self)
        for xml_rec in self:
            _logger.info("Enviando mail documento electronico: %s/%s", counter, total)
            counter += 1
            document = xml_rec.get_current_document()
            # cuando hay xml que se elimino el documento principal, ignorarlos
            if not document:
                documents_sended[xml_rec.id] = True
                continue
            partner = document.partner_id
            invoice_type = ""
            # procesar los modelos que son de account.invoice(facturas, NC, ND)
            if document._name == 'account.move':
                invoice_type = document.get_invoice_type(document.type,
                                                         document.l10n_ec_debit_note,
                                                         document.l10n_ec_liquidation)
            elif document._name == 'account.retention':
                invoice_type = 'withhold_purchase'
            elif document._name == 'stock.picking':
                invoice_type = 'delivery_note'
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
                send_mail_for_document = FIELD_FOR_SEND_MAIL_DOCUMENT[invoice_type] and getattr(company,
                                                                                                FIELD_FOR_SEND_MAIL_DOCUMENT[
                                                                                                    invoice_type],
                                                                                                False) or False
                if not send_mail_for_document:
                    documents_no_sended[xml_rec.id] = True
                    if self.env.context.get('from_function', False):
                        _logger.info(
                            "No esta habilitado el envio de correos para los documentos tipo: %s, verifique su configuracion",
                            document.get_document_string())
                    else:
                        raise UserError(
                            "No esta habilitado el envio de correos para los documentos tipo: %s, verifique su configuracion" % document.get_document_string())
                    continue
                if document.action_sent_mail():
                    documents_sended[xml_rec.id] = True
                else:
                    documents_no_sended[xml_rec.id] = True
            except Exception as e:
                error = self._clean_str(tools.ustr(e))
                documents_no_sended[xml_rec.id] = True
                if self.env.context.get('from_function', False):
                    _logger.warning("Error send mail to partner. ERROR: %s", error)
                else:
                    raise
        if self.env.context.get('from_function', False):
            return list(documents_sended.keys()), list(documents_no_sended.keys())
        else:
            return True

    def process_document_electronic(self, send_file=True):
        """
        Funcion para procesar los documentos(crear xml, firmar, autorizar y enviar mail al cliente)
        """
        # para los documentos electronicos firmados que son documentos externos,
        # no debe enviarlo a autorizar, para esto existira otra tarea cron y asi ganar en rendimiento
        if 'sign_now' in self.env.context and not self.env.context.get('sign_now', False):
            send_file = False
        # si se hace el proceso electronico completamente
        if send_file:
            # enviar a crear el xml
            xml_to_sign, xml_to_notify = self.text_write_binary()
            if xml_to_sign:
                # enviar a firmar el xml
                xml_to_sign.test_sing_xml_file()
                # enviar a autorizar el xml(si se autorizo, enviara el mail a los involucrados)
                xml_to_sign.test_send_file()
        else:
            # solo enviar a crear el xml con la clave de acceso,
            # una tarea cron se debe encargar de calcular datos calculados y continuar con el proceso electronico
            self.text_write_binary()
        return True

    @api.model
    def send_documents_offline(self):
        """
        Procesar los documentos emitidos en modo offline
        """
        company = self.env.user.company_id
        ctx = self.env.context.copy()
        # pasar flag para que los errores salgan x log y no por excepcion
        ctx['call_from_cron'] = True
        ctx['cron_process'] = True
        # pasar flag para que en caso de no autorizar, no me cambie estado del documento y seguir intentado
        ctx['no_change_state'] = True
        xml_recs = self.with_context(ctx).search([
            ('state', '=', 'draft'),
            ('external_document', '=', False),
            ('type_conection_sri', '=', 'offline'),
        ], order="number_document", limit=company.cron_process)
        # si no hay documentos evitar establecer conexion con el SRI
        if not xml_recs:
            return True
        xml_field = 'file_signed'
        type_environment = self._get_environment(company) == '1' and 'test' or 'production'
        receipt_client = self.get_current_wsClient('ws_receipt_' + type_environment)
        auth_client = self.get_current_wsClient('ws_auth_' + type_environment)
        counter = 1
        total = len(xml_recs)
        xml_to_notify_no_autorize = self.browse()
        xml_to_notify2 = OrderedDict()
        xml_to_notify = OrderedDict()
        for xml_data in xml_recs:
            _logger.info("Procesando documentos offline: %s de %s", counter, total)
            counter += 1
            document = xml_data.get_current_document()
            if not document:
                continue
            # enviar a crear el xml, si no devuelve nada es xq no paso la validacion y no debe firmarse
            xml_to_sign, xml_to_notify2 = xml_data.text_write_binary()
            if xml_to_notify2:
                xml_to_notify.update(xml_to_notify2)
            if not xml_to_sign:
                continue
            # enviar a firmar el xml
            xml_data.test_sing_xml_file()
            # enviar a autorizar el xml(si se autorizo, enviara el mail a los involucrados)
            response = self._send_xml_data_to_valid(xml_data.id, xml_field, receipt_client, auth_client)
            ok, messages, raise_error, previous_authorized = self._process_response_check(xml_data.id, response)
            # si recibio la solicitud, enviar a autorizar
            if ok:
                response = self.with_context(ctx)._send_xml_data_to_autorice(xml_data.id, xml_field, auth_client)
                ok, messages = self.with_context(ctx)._process_response_autorization(xml_data.id, response)
            self.with_context(ctx)._create_messaje_response(xml_data.id, messages, ok, raise_error)
            # TODO: si no se puede autorizar, que se debe hacer??
            # por ahora, no hago nada para que la tarea siga intentando en una nueva llamada
            if not ok and messages:
                xml_to_notify_no_autorize |= xml_data
        if xml_to_notify_no_autorize:
            template = self.env.ref('ecua_documentos_electronicos.et_documents_electronics_to_notify')
            ctx = self.env.context.copy()
            ctx['xml_to_notify'] = xml_to_notify_no_autorize
            ctx['title'] = "Los siguientes Documentos no se han podido autorizar con el SRI, " \
                           "es necesario que los revise, corrija y envie manualmente de lo contrario no se autorizaran:"
            template.with_context(ctx).action_sent_mail(company)
        if xml_to_notify:
            template = self.env.ref('ecua_documentos_electronicos.et_documents_electronics_no_valid')
            ctx = self.env.context.copy()
            ctx['xml_to_notify'] = xml_to_notify
            template.with_context(ctx).action_sent_mail(company)
        return True

    @api.model
    def _get_documents_rejected(self, company):
        '''
        Buscar los documentos rechazados y filtrar los que tengan documento asociado
        algunos xml electronicos se elimina el documento original y se quedan huerfanos
        '''
        xml_recs = self.search([('state', 'in', ('returned', 'rejected'))], limit=company.cron_process)
        xml_recs = xml_recs.filtered(lambda x: x.get_current_document())
        return xml_recs

    @api.model
    def send_documents_rejected(self):
        """
        Enviar mail de documentos rechazados o devueltos
        """
        company = self.env.user.company_id
        xml_rejected = self._get_documents_rejected(company)
        if xml_rejected:
            template = self.env.ref('ecua_documentos_electronicos.et_documents_electronics_to_notify')
            ctx = self.env.context.copy()
            ctx['xml_to_notify'] = xml_rejected
            ctx[
                'title'] = "Los siguientes Documentos presentan problemas y han sido rechazados por el SRI, reviselos y corrija manualmente:"
            template.with_context(ctx).action_sent_mail(company)
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
        invoice_line_model = self.env['account.move.line']
        # pasar flag para que al firmar el documento, y estaba en contingencia, me cambie el estado
        ctx['skip_contingency'] = True
        ctx['call_from_cron'] = True
        ctx['cron_process'] = True
        # No se debe verificar constantemente en que estado esta
        ctx['emission'] = '1'
        xml_recs = self.search([('state', '=', 'contingency')], limit=company.cron_process)
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
            document = xml_rec.get_current_document()
            if document:
                res_model_name = document._name
                ctx_invoice['active_ids'] = [document.ids]
                ctx_invoice['active_id'] = document.id
                # si es facturas enviar a calcular los campos calculados de las lineas
                # luego los campos calculados de la factura
                # y por ultimo enviar a calcular los impuestos
                if res_model_name == 'account.move':
                    invoice_line_recs = invoice_line_model.search([('invoice_id', '=', document.id)])
                    if invoice_line_recs:
                        invoice_line_recs.write({})
                document.with_context(ctx_invoice).write({})
                if res_model_name == 'account.move':
                    document.with_context(ctx_invoice).compute_taxes()
                xml_rec.write({'fields_function_calculate': True})
        # TODO: debo cambiar la clave de contingecia antes de reanudar el proceso o no???
        # si es asi, cambiarla antes de llamar a la funcion, ya que si tiene clave, trabaja sobre esa clave
        if xml_recs:
            xml_recs.with_context(ctx).process_document_electronic()
        return True

    @api.model
    def send_documents_waiting_autorization(self):
        """
        Procesar documentos que no fueron autorizados
        pero recibieron error 70(en espera de autorizacion)
        los cuales no debe volver a enviar a autorizar,
        solo esperar que sean confirmada su autorizacion
        """
        company = self.env.user.company_id
        xml_recs = self.search([('state', '=', 'waiting')], limit=company.cron_process)
        # en algunas ocaciones los documentos se envian a autorizar, pero se quedan como firmados
        # buscar los documentos firmados que se hayan enviado a autorizar para verificar si fueron autorizados o no
        xml_signed_recs = self.search([('state','=','signed')])
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
        if not xml_recs:
            return True
        xml_field = 'file_signed'
        ctx = self.env.context.copy()
        # pasar flag para que en caso de no autorizar, no me cambie estado del documento y seguir intentado
        ctx['no_change_state'] = True
        type_environment = self._get_environment(company) == '1' and 'test' or 'production'
        receipt_client = self.get_current_wsClient('ws_receipt_' + type_environment)
        auth_client = self.get_current_wsClient('ws_auth_' + type_environment)
        counter = 1
        total = len(xml_recs)
        xml_to_notify = self.browse()
        for xml_data in xml_recs:
            _logger.info("Procesando documentos en espera de autorizacion: %s de %s", counter, total)
            counter += 1
            document = xml_data.get_current_document()
            if not document:
                continue
            response = self._send_xml_data_to_valid(xml_data.id, xml_field, receipt_client, auth_client)
            ok, messages, raise_error, previous_authorized = self._process_response_check(xml_data.id, response)
            # si recibio la solicitud, enviar a autorizar
            if ok:
                response = self.with_context(ctx)._send_xml_data_to_autorice(xml_data.id, xml_field, auth_client)
                ok, messages = self.with_context(ctx)._process_response_autorization(xml_data.id, response)
            self.with_context(ctx)._create_messaje_response(xml_data.id, messages, ok, raise_error)
            # TODO: si no se puede autorizar, que se debe hacer??
            # por ahora, no hago nada para que la tarea siga intentando en una nueva llamada
            if not ok and messages:
                xml_to_notify |= xml_data
        if xml_to_notify:
            template = self.env.ref('ecua_documentos_electronicos.et_documents_electronics_to_notify')
            ctx = self.env.context.copy()
            ctx['xml_to_notify'] = xml_to_notify
            ctx['title'] = "Los siguientes Documentos no se han podido autorizar con el SRI, " \
                           "es necesario que los revise, corrija y envie manualmente de lo contrario no se autorizaran:"
            template.with_context(ctx).action_sent_mail(company)
        return True

    @api.model
    def send_mail_to_partner(self):
        company = self.env.user.company_id
        if company.type_environment != 'production':
            _logger.info(
                "Envio de correos electronicos solo en ambiente de produccion, por favor verifique su configuracion")
            return
        date_from = company.send_mail_from
        if not date_from:
            date_from = fields.Datetime.now()
        ctx = self.env.context.copy()
        ctx['from_function'] = True
        extra_where = []
        if not company.send_mail_invoice:
            extra_where.append("xml_data.invoice_out_id IS NULL")
        if not company.send_mail_credit_note:
            extra_where.append("xml_data.credit_note_out_id IS NULL")
        if not company.send_mail_debit_note:
            extra_where.append("xml_data.debit_note_out_id IS NULL")
        if not company.send_mail_liquidation:
            extra_where.append("xml_data.liquidation_id IS NULL")
        if not company.send_mail_remision:
            extra_where.append("xml_data.delivery_note_id IS NULL")
        if not company.send_mail_retention:
            extra_where.append("xml_data.withhold_id IS NULL")
        SQL = """SELECT xml_data.id
                        FROM sri_xml_data xml_data
                        INNER JOIN res_partner rp ON rp.id = xml_data.partner_id
                        WHERE xml_data.state = 'authorized' AND rp.type_ref != 'consumidor'
                            AND (xml_data.send_mail=false OR xml_data.send_mail IS NULL) """ \
              + (extra_where and " AND " + " AND ".join(extra_where) or ' ') + """
                            AND xml_data.authorization_date >= %(date_from)s
                        ORDER BY xml_data.id
                        LIMIT %(max_limit)s"""
        self.env.cr.execute(SQL, {
            'date_from': date_from,
            'max_limit': company.cron_process,
        })
        xml_ids = [x[0] for x in self.env.cr.fetchall()]
        if xml_ids:
            documents_sended, documents_no_sended = self.with_context(
                ctx).browse(xml_ids).test_send_mail_partner()
            if documents_sended:
                SQL = "UPDATE sri_xml_data SET send_mail=true WHERE id IN %(xml_ids)s"
                self.env.cr.execute(SQL, {'xml_ids': tuple(documents_sended)})
                # enviar a crear usuario de los que aun no tienen
                self.browse(documents_sended).create_login_for_partner()
            if documents_no_sended:
                SQL = "UPDATE sri_xml_data SET send_mail=false WHERE id IN %(xml_ids)s"
                self.env.cr.execute(
                    SQL, {'xml_ids': tuple(documents_no_sended)})
        return True

    def create_login_for_partner(self):
        portal_model = self.env['portal.wizard']
        if not self.env.user.company_id.create_login_for_partners:
            return False
        partners = self.mapped('partner_id').filtered(lambda x: not x.user_ids and x.type_ref != 'consumidor')
        if partners:
            ctx = self.env.context.copy()
            ctx['active_model'] = 'res.partner'
            ctx['active_ids'] = partners.ids
            ctx['active_id'] = partners[0].id
            user_changes = []
            for partner in partners.sudo():
                user_changes.append((0, 0, {
                    'partner_id': partner.id,
                    'email': partner.email,
                    'in_portal': True,
                }))
            wizard = portal_model.with_context(ctx).create({'user_ids': user_changes})
            try:
                wizard.action_apply()
            except Exception as e:
                _logger.info(tools.ustr(e))
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
            raise UserError(
                "Tipo de archivo no valido, se permite signed, authorized. Por favor verifique")
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
                document_number = xml_rec.invoice_out_id.l10n_latam_document_number
                document_id = xml_rec.invoice_out_id.id
            elif xml_rec.credit_note_out_id:
                document_type = 'nc'
                document_number = xml_rec.credit_note_out_id.l10n_latam_document_number
                document_id = xml_rec.credit_note_out_id.id
            elif xml_rec.debit_note_out_id:
                document_type = 'nd'
                document_number = xml_rec.debit_note_out_id.l10n_latam_document_number
                document_id = xml_rec.debit_note_out_id.id
            elif xml_rec.liquidation_id:
                document_type = 'liq'
                document_number = xml_rec.liquidation_id.l10n_latam_document_number
                document_id = xml_rec.liquidation_id.id
            elif xml_rec.delivery_note_id:
                document_type = 'gr'
                document_number = xml_rec.delivery_note_id.document_number
                document_id = xml_rec.delivery_note_id.id
            elif xml_rec.withhold_id:
                document_type = 're'
                document_number = xml_rec.withhold_id.document_number
                document_id = xml_rec.withhold_id.id
            file_name = "%s_%s_%s_%s.xml" % (document_id, document_type, document_number, file_type)
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
            raise UserError(
                "Debe configurar la ruta para guardar los documentos electronicos. Por favor verifique en la configuracion de compañia")
        file_data = ""
        full_path = os.path.join(root_path, file_name)
        full_path = os.path.normpath(full_path)
        if os.path.isfile(full_path):
            try:
                file_save = open(full_path, "r")
                file_data = file_save.read()
                file_save.close()
            except IOError:
                print(("No se puede leer el archivo %s, verifique permisos en la ruta %s!" % (file_name, root_path)))
        else:
            raise UserError("Archivo %s no encontrado." % (file_name))
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
            raise UserError(
                "Debe configurar la ruta para guardar los documentos electronicos. Por favor verifique en la configuracion de compañia")
        full_path = os.path.join(root_path, file_name)
        full_path = os.path.normpath(full_path)
        # TODO: si el archivo ya existe, sobreescribirlo completamente
        try:
            file_save = open(full_path, "w")
            file_save.write(file_content)
            file_save.close()
        except IOError:
            _logger.warning(_("No se puede escribir en el archivo %s, verifique permisos en la ruta %s!" % (
                file_name, root_path)))
        return full_path

    def get_file_to_wizard(self):
        '''
        @param file_type: str, tipo de documento, se permiten(file_xml, file_signed, file_authorized)
        '''
        self.ensure_one()
        wizard_model = self.env['wizard.xml.get.file']
        util_model = self.env['odoo.utils']
        file_type = self.env.context.get('file_type', 'file_xml')
        file_data = base64.encodebytes(self.get_file(self.id, file_type).encode())
        ctx = self.env.context.copy()
        ctx['active_model'] = self._name
        ctx['active_ids'] = self.ids
        ctx['active_id'] = self.ids and self.ids[0] or False
        if not file_data:
            raise UserError("No existe el fichero, no puede ser mostrado")
        else:
            wizard_rec = wizard_model.create({
                'name': "%s_%s.xml" % (self.number_document, file_type),
                'file_data': file_data,
                'file_type': file_type,
            })
            res = util_model.with_context(ctx).show_wizard(wizard_model._name, 'wizard_xml_get_file_form_view',
                                                           'Descargar Archivo')
            res['res_id'] = wizard_rec.id
            return res

    def unlink(self):
        for xml_data in self:
            # si el documento no esta en borrador no permitir eliminar
            if xml_data.state != 'draft':
                # si esta cancelado, pero no tengo numero de autorizacion para cancelar, permitir eliminar
                if xml_data.state == 'cancel' and not xml_data.authorization_to_cancel:
                    continue
                raise UserError("No puede eliminar registros a menos que esten en estado borrador")
        res = super(SriXmlData, self).unlink()
        return res

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        new_domain = []
        for domain in args:
            if len(domain) == 3:
                # reemplazar ilike o like por el operador =
                # mejora el rendimiento en busquedas
                if domain[0] in self.fields_size and len(domain[2]) == self.fields_size[domain[0]] and domain[1] in (
                        'like', 'ilike'):
                    new_domain.append((domain[0], '=', domain[2]))
                    continue
                else:
                    new_domain.append(domain)
            else:
                new_domain.append(domain)
        res = super(SriXmlData, self)._search(new_domain, offset=offset, limit=limit, order=order, count=count,
                                              access_rights_uid=access_rights_uid)
        return res

    def get_electronic_logo_image(self):
        self.ensure_one()
        if self.agency_id.electronic_logo:
            return self.agency_id.electronic_logo
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
        template_mail_docs_no_autorization = self.env.ref('ecua_documentos_electronicos.mail_documents_no_autorization')
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


class SriXmlDataMessageLine(models.Model):
    _name = 'sri.xml.data.message.line'
    _description = 'Mensajes S.R.I.'
    _rec_name = 'message'

    xml_id = fields.Many2one('sri.xml.data', 'XML Data',
        index=True, auto_join=True, ondelete="cascade")
    message_code_id = fields.Many2one(
        'sri.error.code', 'Código de Mensaje', index=True, auto_join=True)
    message_type = fields.Char('Tipo', size=64)
    other_info = fields.Text(string='Información Adicional')
    message = fields.Text(string='Mensaje')
    create_date = fields.Datetime('Fecha de Creación', readonly=True)
    write_date = fields.Datetime('Ultima actualización', readonly=True)


class SriXmlDataSendTry(models.Model):
    _name = 'sri.xml.data.send.try'
    _description = 'Intentos de envio a SRI'

    xml_id = fields.Many2one('sri.xml.data', 'XML Data',
        index=True, auto_join=True, ondelete="cascade")
    send_date = fields.Datetime('Send Date')
    response_date = fields.Datetime('Response Date')
    type_send = fields.Selection([
        ('send', 'Enviado a Autorizar'),
        ('check', 'Verificar Clave de Acceso'),
    ], string='Tipo', index=True, readonly=True, default='send')
