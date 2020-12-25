from odoo import fields, models


class L10nEcCommonDocument(models.AbstractModel):
    _name = "l10n_ec.common.document"
    _description = "Abstract Class for Ecuadorian documents"

    l10n_ec_point_of_emission_id = fields.Many2one(
        comodel_name="l10n_ec.point.of.emission",
        string="Point of Emission",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    l10n_ec_agency_id = fields.Many2one(
        comodel_name="l10n_ec.agency",
        string="Agency",
        related="l10n_ec_point_of_emission_id.agency_id",
        store=True,
    )
    l10n_ec_base_iva = fields.Float(string="Base IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_0 = fields.Float(string="Base IVA 0", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_iva = fields.Float(string="IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_discount_total = fields.Float(string="Total Discount", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_currency = fields.Float(string="Base IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_0_currency = fields.Float(string="Base IVA 0", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_iva_currency = fields.Float(string="IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_discount_total_currency = fields.Float(
        string="Total Discount", compute="_compute_l10n_ec_amounts", store=True
    )

    def _compute_l10n_ec_amounts(self):
        # esta funcion debe ser implementada en los modulos que hereden de esta clase
        # (account.move, purchase.order, sale.order, pos.order, etc)
        pass


class L10nEcCommonDocumentLine(models.AbstractModel):
    _name = "l10n_ec.common.document.line"
    _description = "Abstract Class for Ecuadorian documents details"

    l10n_ec_base_iva = fields.Float(string="Base IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_0 = fields.Float(string="Base IVA 0", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_iva = fields.Float(string="IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_discount_total = fields.Float(string="Total Discount", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_currency = fields.Float(string="Base IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_base_iva_0_currency = fields.Float(string="Base IVA 0", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_iva_currency = fields.Float(string="IVA", compute="_compute_l10n_ec_amounts", store=True)
    l10n_ec_discount_total_currency = fields.Float(
        string="Total Discount", compute="_compute_l10n_ec_amounts", store=True
    )
    # campo para descuentos adicionales, esto se usara solo para reportes, para distribuir el valor de lineas negativas
    # no sera campo calculado para evitar recalculos innecesarios, solo se hara una vez en el post
    l10n_ec_discount_additional = fields.Float(string="Additional Discount")

    def _compute_l10n_ec_amounts(self):
        # esta funcion debe ser implementada en los modulos que hereden de esta clase
        # (account.move.line, purchase.order.line, sale.order.line, pos.order.line, etc)
        pass
