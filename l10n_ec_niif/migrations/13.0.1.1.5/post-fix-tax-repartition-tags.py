import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    AccountTags = env["account.account.tag"]
    tax_list = [
        ("tax_346", {"tax": ["tag_f103_396"]}),
    ]
    all_company = env["res.company"].search([])
    for company in all_company:
        for tax_idxml, repartition_data in tax_list:
            try:
                tax_id_xml = f"l10n_ec_niif.{company.id}_{tax_idxml}"
                current_tax = env.ref(tax_id_xml, False)
                if not current_tax:
                    continue
                for repartition_type, tags_list in repartition_data.items():
                    tags = AccountTags.browse()
                    for tag_idxml in tags_list:
                        tag = env.ref(f"l10n_ec_niif.{tag_idxml}", False)
                        if tag:
                            tags |= tag
                    if not tags:
                        continue
                    current_tax.invoice_repartition_line_ids.filtered(
                        lambda x: x.repartition_type == repartition_type
                    ).write(
                        {
                            "tag_ids": [(6, 0, tags.ids)],
                        }
                    )
                    current_tax.refund_repartition_line_ids.filtered(
                        lambda x: x.repartition_type == repartition_type
                    ).write(
                        {
                            "tag_ids": [(6, 0, tags.ids)],
                        }
                    )
            except Exception as ex:
                _logger.warning(tools.ustr(ex))
