# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import UserError
import datetime


class TestModule(common.TransactionCase):
    def setUp(self):
        super(TestModule, self).setUp()

        self.test_obj1 = self.env['l10n_ec.agency']
        self.test_agency1 = self.test_obj1.create({
            'name': 'Agency001',
            'number': 999,
            'active': True,
        })
        self.test_agency2 = self.test_obj1.create({
            'name': 'Agency002',
            'number': 998,
            'active': False,
        })

        self.test_obj2 = self.env['l10n_ec.point.of.emission']
        self.test_pofe1 = self.test_obj2.create({
            'name': 'PofE001',
            'number': '001',
            'agency_id': self.test_agency1.id,
            'type_emission': 'pre_printed',
        })

        self.test_pofe2 = self.test_obj2.create({
            'name': 'PofE002',
            'number': '001',
            'agency_id': self.test_agency2.id,
            'type_emission': 'pre_printed',
        })

        self.test_obj3 = self.env['l10n_ec.sri.authorization']
        self.test_auth1 = self.test_obj3.create({
            'number': 'AUTH001',
            'start_date': '2020-8-1',
            'expiration_date': '2020-8-20',
            'active': True,
        })

        self.test_auth1 = self.test_obj3.create({
            'number': 'AUTH001',
            'start_date': '2020-9-1',
            'expiration_date': '2020-9-20',
            'active': True,
        })

        self.test_obj4 = self.env['l10n_ec.sri.authorization.line']
        self.test_doc1 = self.test_obj4.create({
            'document_type': 'invoice',
            'authorization_id': self.test_auth1.id,
            'first_sequence': '1',
            'last_sequence': '100',
            'point_of_emission_id': self.test_pofe1.id,
        })

        self.test_obj5 = self.env['account.move']
        self.test_invoice1 = self.test_obj5.create({
            'l10n_ec_point_of_emission_id': self.test_pofe1.id,
            'l10n_ec_agency_id': self.test_agency1.id,
            'l10n_ec_authorization_line_id': self.test_doc1.id,
        })

    def test_creation_data(self):
        self.assertEqual(self.test_agency1.name, "Agency001", 'Agency name does not match')
        self.assertEqual(self.test_agency1.number, "999", 'Agency number does not match')
        #SUCCESSFUL AGENCY

        self.assertEqual(self.test_pofe1.name, "PofE001", 'PofE name does not match')
        self.assertEqual(self.test_pofe1.number, "001", 'PofE number does not match')
        self.assertEqual(self.test_pofe1.agency_id.id, self.test_agency1.id, 'Agency/PofE relationship is wrong')
        self.assertIn(self.test_pofe1.type_emission, ['electronic', 'pre_printed', 'auto_printer'], 'The type of issue is not within the established rates')
        #2 SUCCESSFULLY POINT OF EMISSION

        self.assertEqual(self.test_auth1.number, "AUTH001", 'Authorization name does not match')
        self.assertEqual(self.test_auth1.start_date, datetime.date(2020, 8, 1), 'Start date does not match')
        self.assertEqual(self.test_auth1.expiration_date, datetime.date(2020, 8, 20), 'The effective date does not match')
        #3 SUCCESSFULLY AUTHORIZATION

        self.assertEqual(self.test_doc1.point_of_emission_id.id, self.test_pofe1.id, 'The Document/PofE relationship is incorrect')
        self.assertEqual(self.test_doc1.authorization_id.id, self.test_auth1.id, 'The Document/authorization relationship is incorrect')
        self.assertEqual(self.test_doc1.first_sequence, 1, 'The first sequence number does not match')
        self.assertEqual(self.test_doc1.last_sequence, 100, 'The last sequence number does not match')
        self.assertIn(self.test_doc1.document_type, ['invoice', 'withholding', 'liquidation', 'credit_note', 'debit_note'],'he document type is not within the established types')
        #4 SUCCESSFULLY DOCUMENT

        self.assertEqual(self.test_invoice1.l10n_ec_point_of_emission_id.id, self.test_pofe1.id, 'The PofE/Invoice relationship is incorrect')
        self.assertEqual(self.test_invoice1.l10n_ec_agency_id.id, self.test_agency1.id, 'The Agency/Invoice relationship is incorrect')
        self.assertEqual(self.test_invoice1.l10n_ec_authorization_id.id, self.test_auth1.id, 'The Authorization/Invoice relationship is incorrect')
        #5 SUCCESSFUL INVOICE

    def test_relationship_active_fiel_agency_pofe(self):
        self.assertIs(self.test_pofe2.active, self.test_agency2.active, 'The relationship of the active field of the Agency / PofE is incorrect')
        #6 Check the relationship of the "active" field in the Agency and the PofE

    def test_delete_agency_with_invoice(self):
        """User should never be able to delete a agency with invoice"""
        with self.assertRaises(UserError):
            self.test_agency1.unlink()

    def test_delete_authorization_with_invoice(self):
        """User should never be able to delete a authorization with invoice"""
        with self.assertRaises(UserError):
            self.test_auth1.unlink()

    def test_delete_authorization_with_invoice_see_error(self):
        """User should never be able to delete a authorization with invoice"""
        with self.assertRaises(UserError):
           self.env['l10n_ec.sri.authorization'].search([('id', '=', self.test_auth1.id)]).unlink()

    def test_duplicate_or_cross_date_ranges(self):
        with self.assertRaises(UserError):
            self.test_auth2.write({
                'start_date': '2020-8-1',
                'expiration_date': '2020-8-20',
            })
