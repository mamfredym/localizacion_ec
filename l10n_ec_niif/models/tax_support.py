from odoo import fields, models


class TaxSupport(models.Model):

    _name = "l10n_ec.tax.support"
    _description = "Ecuadorian Tax Support"

    code = fields.Char(
        string="Código de Sustento Tributario",
        required=True,
        help="",
    )
    name = fields.Char(
        string="Descripción de Sustento Tributario",
        required=True,
        help="",
    )
    document_type_ids = fields.Many2many(
        "l10n_latam.document.type",
        string="Document Types",
        help="",
    )

    def _name_search(self, name, args=None, operator="ilike", limit=100, name_get_uid=None):
        args = args or []
        recs = self.browse()
        res = super(TaxSupport, self)._name_search(name, args, operator, limit, name_get_uid)
        if not res and name:
            recs = self.search([("name", operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search([("code", operator, name)] + args, limit=limit)
            if recs:
                res = models.lazy_name_get(self.browse(recs.ids).with_user(name_get_uid)) or []
        return res

    def name_get(self):
        res = []
        for r in self:
            name = "{} - {}".format(r.code, r.name)
            res.append((r.id, name))
        return res


TaxSupport()
