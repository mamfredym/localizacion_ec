from odoo import models, api, fields, _
from odoo.exceptions import UserError
import re

class L10nLatamDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    def _format_document_number(self, document_number):
        self.ensure_one()
        if self.country_id != self.env.ref('base.ec'):
            return super()._format_document_number(document_number)
        if not document_number:
            return False
        if re.match('(\d{3})+\-(\d{3})+\-(\d{9})', document_number):
            raise UserError(_(u'Ecuadorian Document must be like 001-001-123456789'))
        return document_number
