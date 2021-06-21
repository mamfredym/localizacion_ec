from datetime import datetime

from dateutil.relativedelta import relativedelta

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron_rejected = env.ref("l10n_ec_niif.ir_cron_xml_rejected", False)
    if cron_rejected:
        cron_rejected.write(
            {
                "interval_type": "days",
                "interval_number": 1,
                "nextcall": datetime.now() + relativedelta(days=1, hour=13, minute=0, second=0),
            }
        )
