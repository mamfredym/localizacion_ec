# -*- encoding: utf-8 -*-

from odoo.tools.translate import _
from odoo.exceptions import Warning

def get_document_type(invoice_type):
    """
    Devolver el tipo de documento, el que se usa en los tipo de documento de las autorizaciones
    @param invoice_type: el tipo de factura(out_invoice. out_refund, in_invoice, in_refund, liquidation)
    @return: str, tipo de documento como lo espera los documentos de autorizaciones
    """
    document_type = ''
    #liquidacion de compras
    if invoice_type == 'liquidation':
        document_type = 'liquidation'
    #facturas
    elif invoice_type in ('out_invoice', 'in_invoice'):
        document_type = 'invoice'
    #notas de credito
    elif invoice_type in ('out_refund', 'in_refund'):
        document_type = 'credit_note'
    #Notas de debito
    elif invoice_type in ('debit_note_in', 'debit_note_out'):
        document_type = 'debit_note'
    elif invoice_type == 'invoice_reembolso':
        document_type = 'invoice_reembolso'
    elif invoice_type in ('withhold_sale','withhold_purchase'):
        document_type = 'withholding'
    elif invoice_type == 'delivery_note':
        document_type = 'delivery_note'
    else:
        raise Warning(_("Tipo de Factura/Documento: %s no es válido, por favor verique, get_document_type") % (invoice_type))
    return document_type

def get_invoice_type(invoice_type, debit_note=False, liquidation=False):
    """
    Devolver el tipo de factura
    con el concepto de notas de debito y liquidacion de compras, 
    las facturas de clientes pueden ser notas de debito
    y las facturas de proveedor pueden ser liquidacion de compras
    @param invoice_type: para facturas, el tipo de factura(out_invoice. out_refund, in_invoice, in_refund)
    @param debit_note: Boolean True si es nota de debito(segun el invoice_type se determina si es ND de cliente o de proveedor)
    @param liquidation: Boolean True si es liquidacion de compras
    @return: str, tipo de factura considerando los dos tipos de documentos adicionales(ND y liquidacion de compras)
    """
    document_type = ''
    #Factura de Proveedor
    if invoice_type == 'in_invoice' and not debit_note and not liquidation:
        document_type = 'in_invoice'
    #Factura de Cliente
    elif invoice_type == 'out_invoice' and not debit_note:
        document_type = 'out_invoice'
    #NC de Cliente
    elif invoice_type == 'out_refund':
        document_type = 'out_refund'
    #NC de Proveedor
    elif invoice_type == 'in_refund':
        document_type = 'in_refund'
    #Liquidacion
    elif invoice_type == 'in_invoice' and liquidation:
        document_type = 'liquidation'
    #ND Proveedor
    elif invoice_type == 'in_invoice' and debit_note:
        document_type = 'debit_note_in'
    #ND Cliente
    elif invoice_type == 'out_invoice' and debit_note:
        document_type = 'debit_note_out'
    if not document_type:
        raise Warning(_("Tipo de Factura/Documento: %s no es válido, por favor verique, get_invoice_type") % (invoice_type))
    return document_type

def get_invoice_type_reverse(invoice_type):
    """
    Devolver el tipo de factura como esta en el campo que se guarda en la BD indicando si son ND o liquidacion
    con el concepto de notas de debito y liquidacion de compras, 
    las facturas de clientes pueden ser notas de debito
    y las facturas de proveedor pueden ser liquidacion de compras
    @param invoice_type: para facturas, el tipo de factura(out_invoice. out_refund, in_invoice, in_refund, debit_note_in, debit_note_out, liquidacion)
    @return: tuple(invoice_type, debit_note, liquidation)
        Tupla de 3 elementos, el tipo de factura tal como se guarda en la BD
            debit_note si es nota de debito(de cliente o proveedor)
            liquidation si es liquidacion de compras
    """
    invoice_type_reverse = ''
    debit_note, liquidation = False, False
    #Liquidacion
    if invoice_type == 'liquidation':
        invoice_type_reverse = 'in_invoice'
        liquidation = True
        debit_note = False
    #ND Proveedor
    elif invoice_type == 'debit_note_in':
        invoice_type_reverse = 'in_invoice'
        liquidation = False
        debit_note = True
    #ND Cliente
    elif invoice_type == 'debit_note_out':
        invoice_type_reverse = 'out_invoice'
        liquidation = False
        debit_note = True
    #Factura de Proveedor
    elif invoice_type in ('in_invoice', 'invoice_reembolso'):
        invoice_type_reverse = 'in_invoice'
    #Factura de Cliente
    elif invoice_type == 'out_invoice':
        invoice_type_reverse = 'out_invoice'
    #NC de Cliente
    elif invoice_type == 'out_refund':
        invoice_type_reverse = 'out_refund'
    #NC de Proveedor
    elif invoice_type == 'in_refund':
        invoice_type_reverse = 'in_refund'
    elif invoice_type in ('withhold_sale','withhold_purchase'):
        invoice_type_reverse = 'withhold'
    elif invoice_type == 'delivery_note':
        invoice_type_reverse = 'delivery_note'
    else:
        raise Warning(_("Tipo de Factura/Documento: %s no es válido, por favor verique, get_invoice_type_reverse") % (invoice_type))
    return invoice_type_reverse, debit_note, liquidation

def get_invoice_field_report(invoice_type):
    """
    Devolver el nombre del campo que tiene el reporte del documento
    con el concepto de notas de debito y liquidacion de compras, 
    las facturas de clientes pueden ser notas de debito
    y las facturas de proveedor pueden ser liquidacion de compras
    @param invoice_type: para facturas, el tipo de factura(out_invoice. out_refund, in_invoice, in_refund)
    @param debit_note: Boolean True si es nota de debito(segun el invoice_type se determina si es ND de cliente o de proveedor)
    @param liquidation: Boolean True si es liquidacion de compras
    @return: str, tipo de factura considerando los dos tipos de documentos adicionales(ND y liquidacion de compras)
    """
    field_report_name = ''
    #Factura de Cliente
    if invoice_type == 'out_invoice':
        field_report_name = 'report_out_invoice_id'
    #NC de Cliente
    elif invoice_type == 'out_refund':
        field_report_name = 'report_out_refund_id'
    #Liquidacion
    elif invoice_type == 'liquidation':
        field_report_name = 'report_liquidation_id'
    #ND Cliente
    elif invoice_type == 'debit_note_out':
        field_report_name = 'report_debit_note_out_id'
    if not field_report_name:
        raise Warning(_("Tipo de Factura/Documento: %s no es válido, por favor verique. get_invoice_field_report") % (invoice_type))
    return field_report_name

def get_invoice_view_id(invoice_type):
    """
    Devolver el id_xml de la vista para la factura segun el tipo de documento
    @param invoice_type: el tipo de factura considerando los dos tipos de documentos adicionales(ND y liquidacion de compras)
    @return: tuple(module, id_xml), False, False si el tipo de factura no es correcto
    """
    views_data = {'out_invoice': ('account','invoice_form'),
                  'in_invoice': ('account', 'invoice_supplier_form'),
                  'out_refund': ('account','invoice_form'),
                  'in_refund': ('account', 'invoice_supplier_form'),
                  'liquidation': ('account', 'invoice_supplier_form'),
                  'debit_note_out': ('account','invoice_form'),
                  'debit_note_in': ('account', 'invoice_supplier_form'),
                  }
    return views_data.get(invoice_type, (False, False))

def get_document_name(document_type):
    """
    Devolver la descripcion del modelo segun el tipo de documento(el que usa los documentos de autorizaciones)
    @param document_type: el tipo de documento(el que usa los documentos de autorizaciones)
    @return: str, la descripcion del tipo de documento, entendible por el usuario
    """
    document_names = {'invoice': _(u'Factura'),
                      'credit_note': _(u'Nota de Crédito'),
                      'debit_note': _(u'Nota de Débito'),
                      'liquidation': _(u'Liquidación de Compras'),
                      'withholding': _(u'Retención'),
                      'delivery_note': _(u'Guía de Remisión'),
                      'invoice_reembolso': _(u'Reembolso de gasto'),
                      }
    return document_names.get(document_type, '')

def get_model_name(document_type):
    """
    Devolver el nombre del modelo segun el tipo de documento(el que usa los documentos de autorizaciones)
    @param document_type: el tipo de documento(el que usa los documentos de autorizaciones)
    @return: str, el nombre tecnico del tipo de documento para usar ORM
    """
    model_name = {'invoice': 'account.move',
                  'credit_note': 'account.move',
                  'debit_note': 'account.move',
                  'liquidation': 'account.move',
                  'withholding': 'account.retention',
                  'delivery_note': 'account.remision',
                  'invoice_reembolso': 'account.invoice.reembolso'
                  }
    return model_name.get(document_type, '')

def get_field_name(document_type):
    """
    Devolver el nombre del campo que tiene el numero del modelo segun el tipo de documento(el que usa los documentos de autorizaciones)
    @param document_type: el tipo de documento(el que usa los documentos de autorizaciones)
    @return: str, el nombre tecnico del campo que tiene el numero del modelo para usar ORM
    """
    field_name = {'invoice': 'l10n_ec_document_number',
                  'credit_note': 'l10n_ec_document_number',
                  'debit_note': 'l10n_ec_document_number',
                  'liquidation': 'l10n_ec_document_number',
                  'withholding': 'document_number',
                  'delivery_note': 'document_number',
                  'invoice_reembolso': 'number',
                  }
    return field_name.get(document_type, '')

def get_field_authorization(document_type):
    """
    Devolver el nombre del campo que tiene la autorizacion del modelo segun el tipo de documento(el que usa los documentos de autorizaciones)
    @param document_type: el tipo de documento(el que usa los documentos de autorizaciones)
    @return: str, el nombre tecnico del campo que tiene la autorizacion del modelo para usar ORM
    """
    authorization_name = {'invoice': 'authorization_owner_id',
                          'credit_note': 'authorization_owner_id',
                          'debit_note': 'authorization_owner_id',
                          'liquidation': 'authorization_owner_id',
                          'withholding': 'authorization_owner_id',
                          'delivery_note': 'authorization_owner_id',
                          }
    return authorization_name.get(document_type, '')

def get_field_journal(invoice_type):
    """
    Devolver el nombre del campo que tiene la autorizacion del modelo segun el tipo de documento(el que usa los documentos de autorizaciones)
    @param invoice_type: el tipo de factura considerando los dos tipos de documentos adicionales(ND y liquidacion de compras)
    @return: str, el nombre tecnico del campo que tiene el diario en la agencia, para usar ORM
    """
    journal_field_name = {'out_invoice': 'sales_journal_id',
                          'in_invoice': 'purchases_journal_id',
                          'out_refund': 'sales_journal_id',
                          'in_refund': 'purchases_journal_id',
                          'liquidation': 'liquidation_journal_id',
                          'debit_note_in': 'debit_note_purchase_journal_id',
                          'debit_note_out': 'debit_note_sale_journal_id',
                          }
    return journal_field_name.get(invoice_type, '')

def get_domain(invoice_type, include_state=True):
    """
    Devolver un domain para usarse en busquedas segun el tipo de documento(el que usa los documentos de autorizaciones de clientes)
    @param invoice_type: el tipo de documento(el que usa los documentos de autorizaciones de clientes)
    @return: lista de tuplas con domain valido para hacer busquedas con ORM 
    """
    invoice_type_bd, debit_note, liquidation = get_invoice_type_reverse(invoice_type)
    domain_state_data = {'out_invoice': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'out_refund': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'in_refund': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'debit_note_out': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'debit_note_in': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'liquidation': [],
                         'in_invoice': [('state', 'in', ('open', 'paid', 'cancel'))],
                         'withhold_sale': [],
                         'withhold_purchase': [],
                         }
    common_domain = [('type','=', invoice_type_bd),
                     ('l10n_ec_debit_note', '=', debit_note),
                     ('l10n_ec_liquidation', '=', liquidation),
                     ]
    domain_state = []
    if include_state:
        domain_state = domain_state_data.get(invoice_type, [])
    domain_account_invoice = common_domain + domain_state
    domains = {'out_invoice': domain_account_invoice,
               'out_refund': domain_account_invoice,
               'in_refund': domain_account_invoice,
               'debit_note_out': domain_account_invoice,
               'debit_note_in': domain_account_invoice,
               'liquidation': domain_account_invoice,
               'in_invoice': domain_account_invoice,
               'withhold_sale': [('transaction_type', '=', 'sale')],
               'withhold_purchase': [('transaction_type', '=', 'purchase')],
               'delivery_note': [],
               'invoice_reembolso': [],
               }
    
    return domains.get(invoice_type, [])