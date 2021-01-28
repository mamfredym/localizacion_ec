import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    TaxTemplateModel = env["account.tax.template"]
    new_tax_template_id_xml = [
        ("l10n_ec_niif.tax_7_iva"),
        ("l10n_ec_niif.tax_8_iva"),
    ]
    for tax_id_xml in new_tax_template_id_xml:
        try:
            tax_template = TaxTemplateModel.env.ref(tax_id_xml)
            tax_template._generate_tax(env.company)
        except Exception as ex:
            _logger.warning(tools.ustr(ex))
