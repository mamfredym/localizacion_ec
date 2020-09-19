def migrate(cr, version):
    # recuperar el valor de la columna temporal y eliminar el campo temporal
    cr.execute("UPDATE account_journal SET l10n_latam_internal_type = l10n_latam_internal_type_tmp")
    cr.execute("ALTER TABLE account_journal DROP COLUMN l10n_latam_internal_type_tmp")
