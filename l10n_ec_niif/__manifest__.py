{
    'name': 'Ecuador - Accounting IFRS',
    'version': '1.0',
    'description': '''
his is the base module to manage the accounting chart for Ecuador in Odoo.
==============================================================================

Accounting chart and localization for Ecuador.
    ''',
    'category': 'Localization',
    'author': 'Vision Estrategica Cia. Ltda.',
    'website': 'https://www.vision-estrategica.com',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'base_iban',
        'base_vat',
        'l10n_latam_base',
        'l10n_latam_invoice_document',
        'account_accountant',
        'account_debit_note',
                ],
    'data': [
        'security/ir.model.access.csv',
        'data/l10n_latam.document.type.csv',
        'data/l10n_latam_identification_type_data.xml',
        'data/l10n_ec_identification_type_data.xml',
        'data/partner_data.xml',
        'data/account_tag_data.xml',
        'data/l10n_ec_chart_data.xml',
        'data/account.account.template.csv',
        'data/tax_data.xml',
        'data/tax_support_data.xml',
        'data/l10n_ec_chart_post_data.xml',
        'data/bank_data.xml',
        'views/sri_menu.xml',
        'views/res_partner_view.xml',
        'views/tax_support_view.xml',
        'views/identification_type_view.xml',
        'views/account_move_view.xml',
        'views/agency_view.xml',
        'views/authorization_view.xml',
        'views/authorization_supplier_view.xml',
        'views/res_users_view.xml',
        'views/l10n_latam_document_type_view.xml',
        'views/account_journal_view.xml',
        'views/withhold_view.xml',
        'views/res_config_view.xml',
             ],
    'demo': [''],
    'installable': True,
    'auto_install': False,
    'external_dependencies': {
        'python': ['stdnum'],
    }
}