from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # eliminar las vistas de account.move para forzar se vuelvan a crear
    # al eliminar campos y tener varias vistas heredadas que usan esos campos,
    # cuando se actualiza la primer vista se hace el render de las demas vistas heredadas
    # y se obtiene error que ciertos campos no existen
    views_to_unlink = env.ref("l10n_ec_niif.view_move_form_debit", False)
    if views_to_unlink:
        views_to_unlink.unlink()
    # agregar una columna temporal para al final de la actualizacion recuperar el valor de esta columna
    # ya que odoo eliminaria los campos l10n_ec_debit_note y l10n_ec_liquidation
    # actualizamos primero los diarios de ND y liquidacion
    # los restantes se le asume invoice
    cr.execute("ALTER TABLE account_journal ADD COLUMN l10n_latam_internal_type_tmp VARCHAR")
    cr.execute(
        "UPDATE account_journal SET l10n_latam_internal_type_tmp = 'debit_note' " " WHERE l10n_ec_debit_note = true"
    )
    cr.execute(
        "UPDATE account_journal SET l10n_latam_internal_type_tmp = 'liquidation' " " WHERE l10n_ec_liquidation = true"
    )
    cr.execute(
        "UPDATE account_journal SET l10n_latam_internal_type_tmp = 'invoice' "
        " WHERE type IN ('sale', 'purchase') AND l10n_latam_use_documents = true"
        " AND l10n_latam_internal_type_tmp IS NULL"
    )
