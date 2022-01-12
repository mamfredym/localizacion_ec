from odoo import fields, models


class SriXmlInfoAditional(models.Model):
    _name = "sri.xml.info.aditional"
    _description = "Additional Info on RIDE"

    name = fields.Char(string="Name", required=True)
    description = fields.Char(string="Description", required=True)
    move_id = fields.Many2one("account.move", "Account Move", ondelete="cascade")
