def migrate(cr, version):
    cr.execute(
        "UPDATE account_move_line aml SET l10n_latam_document_type_id=am.l10n_latam_document_type_id "
        "FROM  account_move am  "
        "WHERE am.id = aml.move_id AND aml.l10n_latam_document_type_id != am.l10n_latam_document_type_id "
        " AND am.l10n_latam_document_type_id IS NOT NULL;"
    )
