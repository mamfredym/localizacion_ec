 #

from odoo import api, fields, models, SUPERUSER_ID
from odoo.tools.translate import _
from odoo.exceptions import Warning, UserError, ValidationError
from stdnum.ec import ci, ruc


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.depends('country_id')
    def _compute_l10n_ec_foreign(self):
        for partner in self:
            l10n_ec_foreign = False
            if partner.country_id:
                if partner.country_id.code != 'EC':
                    l10n_ec_foreign = True
            partner.l10n_ec_foreign = l10n_ec_foreign

    l10n_ec_foreign = fields.Boolean('Foreign?',
                                     readonly=True, help="", store=True, compute='_compute_l10n_ec_foreign')
    l10n_ec_foreign_type = fields.Selection(
        [('01', 'Persona Natural'),
         ('02', 'Sociedad'),
         ], string='Foreign Type', readonly=False, help="", )
    l10n_ec_business_name = fields.Char('Business Name',
                                        required=False, readonly=False, help="", )
    # Datos para el reporte dinardap
    l10n_ec_sex = fields.Selection([
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ], string='Sex', readonly=False, help="", required=False)
    l10n_ec_marital_status = fields.Selection([
        ('S', 'Soltero(a)'),
        ('C', 'Casado(a)'),
        ('D', 'Divorciado(a)'),
        ('', 'Unión Libre'),
        ('V', 'Viudo(o)'),
    ], string='Civil Status', readonly=False, help="", required=False)
    l10n_ec_input_origins = fields.Selection([('B', 'Empleado Público'),
                                              ('V', 'Empleado Privado'),
                                              ('I', 'Independiente'),
                                              ('A', 'Ama de Casa o Estudiante'),
                                              ('R', 'Rentista'),
                                              ('H', 'Jubilado'),
                                              ('M', 'Remesa del Exterior'),
                                              ], string='Input Origins', readonly=False, help="", required=False)
    l10n_ec_related_part = fields.Boolean(
        'Related Part?', readonly=False, help="", )
    l10n_ec_is_ecuadorian_company = fields.Boolean(
        string="is Ecuadorian Company?", compute="_get_ecuadorian_company")

    @api.depends('company_id.country_id')
    def _get_ecuadorian_company(self):
        for rec in self:
            l10n_ec_is_ecuadorian_company = False
            if rec.company_id and rec.company_id.country_id.code == 'EC':
                l10n_ec_is_ecuadorian_company = True
            rec.l10n_ec_is_ecuadorian_company = l10n_ec_is_ecuadorian_company

    def copy_data(self, default=None):
        if not default:
            default = {}
        default.update({
            'vat': False,
        })
        return super(ResPartner, self).copy_data(default)

    # @api.constrains('vat')
    # def _check_duplicity(self):
    #     for rec in self:
    #         if rec.vat:
    #             other_partner = self.search([
    #                 ('vat', '=', rec.vat),
    #                 ('id', '!=', rec.id),
    #                                         ])
    #             if len(other_partner) >= 1:
    #                 raise Warning(_("The number %s must be unique as VAT") % rec.vat)

    def verify_final_consumer(self, vat):
        b = True
        c = 0
        try:
            for n in vat:
                if int(n) != 9:
                    b = False
                c += 1
            if c == 13:
                return b
        except Exception as e:
            return False

    def check_vat_ec(self, vat):
        if self.verify_final_consumer(vat):
            return self.verify_final_consumer(vat), "Consumidor"
        elif ci.is_valid(vat):
            return ci.is_valid(vat), "Cedula"
        elif ruc.is_valid(vat):
            return ruc.is_valid(vat), "Ruc"
        else:
            return False, False

    @api.constrains('vat', 'country_id')
    def check_vat(self):
        if self.sudo().env.ref('base.module_base_vat').state == 'installed':
            self = self.filtered(
                lambda partner: partner.country_id == self.env.ref('base.ec'))
            for partner in self:
                if partner.vat:
                    valid, vat_type = self.check_vat_ec(partner.vat)
                    if not valid:
                        raise UserError(
                            _('VAT %s is not valid for an Ecuadorian company, ''it must be like this form 17165373411001') % (partner.vat))
            return super(ResPartner, self).check_vat()
        else:
            return True

    @api.depends('vat', 'country_id')
    def _get_l10n_ec_type_sri(self):
        vat_type = ''
        for partner in self:
            if partner.vat:
                dni, vat_type = self.check_vat_ec(partner.vat)
            if partner.country_id:
                if partner.country_id.code != 'EC':
                    vat_type = 'Pasaporte'
            partner.l10n_ec_type_sri = vat_type

    l10n_ec_type_sri = fields.Char('SRI Identification Type',
                                   store=True, readonly=True, compute='_get_l10n_ec_type_sri')

    def write(self, values):
        for partner in self:
            if partner.ref == '9999999999999' and self._uid != SUPERUSER_ID and \
                    ('name' in values
                     or 'vat' in values
                     or 'active' in values
                     or 'country_id' in values):
                raise Warning(_('You cannot modify record of final consumer'))
        return super(ResPartner, self).write(values)

    def unlink(self):
        for partner in self:
            if partner.ref == '9999999999999':
                raise Warning(_("You cannot unlink final consumer"))
        return super(ResPartner, self).unlink()

    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        recs = self.browse()
        res = super(ResPartner, self)._name_search(
            name, args, operator, limit, name_get_uid)
        if not res and name:
            recs = self.search([('vat', operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search(
                    [('l10n_ec_business_name', operator, name)] + args, limit=limit)
            if recs:
                res = models.lazy_name_get(self.browse(
                    recs.ids).with_user(name_get_uid)) or []
        return res

    l10n_ec_authorization_ids = fields.One2many('l10n_ec.sri.authorization.supplier',
                                                'partner_id', string='Third Party Authorizations')

    l10n_ec_email_out_invoice = fields.Boolean('As Follower on Invoice', readonly=False,
                                               default=lambda self: not ("default_parent_id" in self.env.context))
    l10n_ec_email_out_refund = fields.Boolean('As Follower on Credit Note', readonly=False,
                                              default=lambda self: not ("default_parent_id" in self.env.context))
    l10n_ec_email_debit_note_out = fields.Boolean('As Follower on Debit Notes', readonly=False,
                                                  default=lambda self: not ("default_parent_id" in self.env.context))
    l10n_ec_email_delivery_note = fields.Boolean('As Follower Delivery Note', readonly=False,
                                                 default=lambda self: not ("default_parent_id" in self.env.context))
    l10n_ec_email_withhold_purchase = fields.Boolean('As Follower on Withhold', readonly=False,
                                                     default=lambda self: not ("default_parent_id" in self.env.context))


ResPartner()
