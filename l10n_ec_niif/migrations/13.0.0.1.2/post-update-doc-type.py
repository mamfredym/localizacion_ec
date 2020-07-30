def migrate(cr, version):
    cr.execute(
        """UPDATE l10n_ec_point_of_emission_document_sequence SET document_type = 'withhold_purchase'
                    WHERE document_type = 'withholding'"""
    )
