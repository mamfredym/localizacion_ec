from odoo import fields, models, api


class L10nCompanyResolution (models.Model):
    _name = 'l10n_ec.sri.company.resolution'
    _description = 'Company Resolutions'

    company_id = fields.Many2one('res.company', 'Company',
        default=lambda self: self.env.company, required=True, ondelete="cascade")
    resolution = fields.Char('Resolution')
    date_from = fields.Date('Date from')
    date_to = fields.Date('Date to')
    active = fields.Boolean(default=True)
