from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import Warning, UserError, ValidationError
from stdnum.ec import ci, ruc
from stdnum.exceptions import *


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.depends('country_id')
    def _compute_l10_ec_foreign(self):
        for partner in self:
            l10_ec_foreign = False
            if partner.country_id:
                if partner.country_id.code != 'EC':
                    l10_ec_foreign = True
            partner.l10_ec_foreign = l10_ec_foreign

    l10_ec_foreign = fields.Boolean(u'Foreign?',
                                    readonly=True, help=u"", store=True, compute='_compute_l10_ec_foreign')
    l10_ec_foreign_type = fields.Selection(
        [('01', u'Persona Natural'),
         ('02', u'Sociedad'),
         ], string=u'Foreign Type', readonly=False, help=u"", )
    l10_ec_business_name = fields.Char(u'Business Name',
                                       required=False, readonly=False, help=u"", )
    # Datos para el reporte dinardap
    l10_ec_sex = fields.Selection([
        ('M', u'Masculino'),
        ('F', u'Femenino'),
    ], string=u'Sex', readonly=False, help=u"", required=False)
    l10_ec_marital_status = fields.Selection([
        ('S', u'Soltero(a)'),
        ('C', u'Casado(a)'),
        ('D', u'Divorciado(a)'),
        ('U', u'Unión Libre'),
        ('V', u'Viudo(o)'),
                                       ], string=u'Civil Status', readonly=False, help=u"", required=False)
    l10_ec_input_origins = fields.Selection([('B', u'Empleado Público'),
                                      ('V', u'Empleado Privado'),
                                      ('I', u'Independiente'),
                                      ('A', u'Ama de Casa o Estudiante'),
                                      ('R', u'Rentista'),
                                      ('H', u'Jubilado'),
                                      ('M', u'Remesa del Exterior'),
                                      ], string=u'Input Origins', readonly=False, help=u"", required=False)
    l10_ec_related_part = fields.Boolean(u'Related Part?', readonly=False, help=u"", )
    l10_ec_is_ecuadorian_company = fields.Boolean(string="is Ecuadorian Company?", compute="_get_ecuadorian_company")

    @api.depends('company_id.country_id')
    def _get_ecuadorian_company(self):
        l10_ec_is_ecuadorian_company = False
        if self.company_id and self.company_id.country_id.code == 'EC':
            l10_ec_is_ecuadorian_company = True
        self.l10_ec_is_ecuadorian_company = l10_ec_is_ecuadorian_company

    def copy_data(self, default=None):
        if not default:
            default = {}
        default.update({
            'vat': False,
        })
        return super(ResPartner, self).copy_data(default)

    @api.constrains('vat')
    def _check_duplicity(self):
        if self.vat:
            other_partner = self.search([('vat', '=', self.vat)])
            if len(other_partner) > 1:
                raise Warning(_(u"The number %s must be unique as VAT") % self.vat)

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
            self = self.filtered(lambda partner: partner.country_id == self.env.ref('base.ec'))
            for partner in self:
                if partner.vat:
                    valid, vat_type = self.check_vat_ec(partner.vat)
                    if not valid:
                        raise UserError(_('VAT %s is not valid for an Ecuadorian company, ''it must be like this form 17165373411001') % (partner.vat))
            return super(ResPartner, self).check_vat()
        else:
            return True

    @api.depends('vat', 'country_id')
    def _get_l10_ec_type_sri(self):
        vat_type = ''
        for partner in self:
            if partner.vat:
                dni, vat_type = self.check_vat_ec(partner.vat)
            if partner.country_id:
                if partner.country_id.code != 'EC':
                    vat_type = 'Pasaporte'
            partner.l10_ec_type_sri = vat_type

    l10_ec_type_sri = fields.Char(u'SRI Identification Type',
                                  store=True, readonly=True, compute='_get_l10_ec_type_sri')

    def write(self, values):
        for partner in self:
            if partner.ref == '9999999999999' and self._uid != 1 and \
                    ('name' in values or 'vat' in values or 'l10_ec_foreign' in values or 'l10_ec_type_sri' in values):
                raise Warning(_(u'You cannot modify record of final consumer'))
        return super(ResPartner, self).write(values)

    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        recs = self.browse()
        res = super(ResPartner, self)._name_search(name, args, operator, limit, name_get_uid)
        if not res and name:
            recs = self.search([('vat', operator, name)] + args, limit=limit)
            if not recs:
                recs = self.search([('l10_ec_business_name', operator, name)] + args, limit=limit)
            if recs:
                res = models.lazy_name_get(self.browse(recs.ids).with_user(name_get_uid)) or []
        return res


ResPartner()
