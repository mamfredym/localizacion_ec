def migrate(cr, version):
    cr.execute(
        """UPDATE l10n_ec_point_of_emission_document_sequence SET document_type = 'out_invoice'
                    WHERE document_type = 'invoice'"""
    )
    cr.execute(
        """UPDATE l10n_ec_point_of_emission_document_sequence SET document_type = 'out_refund'
                    WHERE document_type = 'credit_note'"""
    )
    cr.execute(
        """UPDATE l10n_ec_point_of_emission_document_sequence SET document_type = 'debit_note_out'
                    WHERE document_type = 'debit_note'"""
    )
