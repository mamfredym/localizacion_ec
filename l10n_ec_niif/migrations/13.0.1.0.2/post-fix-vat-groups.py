from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tax_413 = env.ref("l10n_ec_niif.20_tax_413_iva", False)
    tax_414 = env.ref("l10n_ec_niif.20_tax_414_iva", False)
    tax_415 = env.ref("l10n_ec_niif.20_tax_415_iva", False)
    tax_416 = env.ref("l10n_ec_niif.20_tax_416_iva", False)
    tax_441 = env.ref("l10n_ec_niif.20_tax_441_iva", False)
    tax_516 = env.ref("l10n_ec_niif.20_tax_516_iva", False)
    tax_517 = env.ref("l10n_ec_niif.20_tax_517_iva", False)
    tax_518 = env.ref("l10n_ec_niif.20_tax_518_iva", False)
    tax_541 = env.ref("l10n_ec_niif.20_tax_541_iva", False)
    tax_542 = env.ref("l10n_ec_niif.20_tax_542_iva", False)
    group_iva_0 = env.ref("l10n_ec_niif.tax_group_iva_0", False)
    group_no_apply = env.ref("l10n_ec_niif.tax_group_iva_no_apply", False)
    group_exempt = env.ref("l10n_ec_niif.tax_group_iva_exempt", False)
    if tax_413:
        tax_413.tax_group_id = group_iva_0.id
    if tax_414:
        tax_414.tax_group_id = group_iva_0.id
    if tax_415:
        tax_415.tax_group_id = group_iva_0.id
    if tax_416:
        tax_416.tax_group_id = group_iva_0.id
    if tax_441:
        tax_441.tax_group_id = group_exempt.id
    if tax_516:
        tax_516.tax_group_id = group_iva_0.id
    if tax_517:
        tax_517.tax_group_id = group_iva_0.id
    if tax_518:
        tax_518.tax_group_id = group_iva_0.id
    if tax_541:
        tax_541.tax_group_id = group_no_apply.id
    if tax_542:
        tax_542.tax_group_id = group_exempt.id
