import collections
import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # pasar los valores de la plantilla de impuesto a los impuestos
    # para ello generar un id_xml siguiendo el patron de Odoo al instalar el plan contable
    # modulo.CompanyID_TaxTemplateIdXml
    env = api.Environment(cr, SUPERUSER_ID, {})
    TaxTemplateModel = env["account.tax.template"]
    all_company = env["res.company"].search([])
    all_tax_template = TaxTemplateModel.search([])
    domain = [
        ("model", "=", "account.tax.template"),
        ("res_id", "in", all_tax_template.ids),
    ]
    xml_id_data = env["ir.model.data"].search_read(domain, ["module", "name", "res_id"])
    for company in all_company:
        xml_ids = collections.defaultdict(list)
        for data in xml_id_data:
            xml_ids[data["res_id"]].append(f"{data['module']}.{company.id}_{data['name']}")
        for tax_tmpl in all_tax_template:
            try:
                tax_id_xml = xml_ids.get(tax_tmpl.id, [""])[0]
                if not tax_id_xml:
                    continue
                current_tax = env.ref(tax_id_xml, False)
                if not current_tax:
                    continue
                current_tax.write(
                    {
                        "l10n_ec_ats_code": tax_tmpl.l10n_ec_ats_code,
                        "l10n_ec_xml_fe_code": tax_tmpl.l10n_ec_xml_fe_code,
                    }
                )
            except Exception as ex:
                _logger.warning(tools.ustr(ex))
