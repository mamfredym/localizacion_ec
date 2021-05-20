import logging

from odoo import SUPERUSER_ID, api, tools

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    AccountTags = env["account.account.tag"]
    MoveLines = env["account.move.line"]
    tax_list = [
        ("tax_3440", {"base": ["tag_f103_3440"], "tax": ["tag_f103_3940"]}),
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
                current_tax_moves = MoveLines.search([("tax_line_id", "=", current_tax.id)])
                current_base_moves = MoveLines.search([("tax_ids", "in", current_tax.ids)])
                invoice_base_tags_ids = current_tax.invoice_repartition_line_ids.filtered(
                    lambda x: x.repartition_type == "base"
                ).tag_ids.ids
                refund_base_tags_ids = current_tax.refund_repartition_line_ids.filtered(
                    lambda x: x.repartition_type == "base"
                ).tag_ids.ids
                invoice_tax_tags_ids = current_tax.invoice_repartition_line_ids.filtered(
                    lambda x: x.repartition_type == "tax"
                ).tag_ids.ids
                refund_tax_tags_ids = current_tax.refund_repartition_line_ids.filtered(
                    lambda x: x.repartition_type == "tax"
                ).tag_ids.ids
                current_fiscal_lock_date = company.fiscalyear_lock_date
                current_tax_lock_date = company.tax_lock_date
                if current_fiscal_lock_date:
                    company.fiscalyear_lock_date = None
                if current_tax_lock_date:
                    company.tax_lock_date = None
                if current_tax_moves:
                    refund_moves = current_tax_moves.filtered(lambda x: x.move_id.type in ("out_refund", "in_refund"))
                    normal_moves = current_tax_moves - refund_moves
                    if normal_moves:
                        normal_moves.write(
                            {
                                "tag_ids": invoice_tax_tags_ids and [(6, 0, invoice_tax_tags_ids)],
                            }
                        )
                    if refund_moves:
                        refund_moves.write(
                            {
                                "tag_ids": refund_tax_tags_ids and [(6, 0, refund_tax_tags_ids)],
                            }
                        )
                if current_base_moves:
                    refund_moves = current_base_moves.filtered(lambda x: x.move_id.type in ("out_refund", "in_refund"))
                    normal_moves = current_base_moves - refund_moves
                    if normal_moves:
                        normal_moves.write(
                            {
                                "tag_ids": invoice_base_tags_ids and [(6, 0, invoice_base_tags_ids)],
                            }
                        )
                    if refund_moves:
                        refund_moves.write(
                            {
                                "tag_ids": refund_base_tags_ids and [(6, 0, refund_base_tags_ids)],
                            }
                        )
                company.fiscalyear_lock_date = current_fiscal_lock_date
                company.tax_lock_date = current_tax_lock_date
            except Exception as ex:
                _logger.warning(tools.ustr(ex))
