from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nCompanyResolution(models.Model):
    _name = "l10n_ec.sri.company.resolution"
    _description = "Company Resolutions"
    _rec_name = "resolution"

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.company,
        required=True,
        ondelete="cascade",
    )
    resolution = fields.Char("Resolution", size=6, required=True)
    date_from = fields.Date("Date from", required=True)
    date_to = fields.Date("Date to", required=True)
    active = fields.Boolean(default=True)

    @api.constrains("date_from", "date_to")
    @api.onchange("date_from", "date_to")
    def _check_dates(self):
        for resolution in self:
            if resolution.date_from and resolution.date_to:
                if resolution.date_to < resolution.date_from:
                    raise ValidationError(_("Dates are not valid"))
