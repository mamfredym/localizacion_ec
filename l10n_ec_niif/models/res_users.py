from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class ResUsers(models.Model):
    _inherit = "res.users"

    l10n_ec_agency_ids = fields.Many2many("l10n_ec.agency", string="Allowed Agencies")
    l10n_ec_printer_default_id = fields.Many2one(
        "l10n_ec.point.of.emission",
        string="Default Point of Emission",
        company_dependent=True,
    )

    @api.model
    def get_default_point_of_emission(self, user_id=False, get_all=True, raise_exception=True):
        user = self.env.user
        if user_id:
            user = self.browse(user_id)
        printer_model = self.env["l10n_ec.point.of.emission"]
        res = {
            "default_printer_default_id": printer_model.browse(),
            "all_printer_ids": printer_model.browse(),
        }
        if user.l10n_ec_printer_default_id:
            res["default_printer_default_id"] = user.l10n_ec_printer_default_id
            res["all_printer_ids"] |= user.l10n_ec_printer_default_id
        else:
            for agency in user.l10n_ec_agency_ids:
                for printer in agency.printer_point_ids:
                    res["default_printer_default_id"] = printer
                    res["all_printer_ids"] |= printer
                    break
                break
        if not res["default_printer_default_id"] or get_all:
            for agency in user.l10n_ec_agency_ids:
                for printer in agency.printer_point_ids:
                    res["all_printer_ids"] |= printer
        if (
            not res["default_printer_default_id"]
            and raise_exception
            and self.env.company.country_id.code == "EC"
            and not (user.has_group("base.group_public") or user.has_group("base.group_portal"))
        ):
            raise UserError(
                _(
                    "Your user does not have the permissions "
                    "configured correctly (Agency, Point of emission), please check with the administrator"
                )
            )
        return res
