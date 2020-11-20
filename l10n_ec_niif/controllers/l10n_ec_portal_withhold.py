import base64
from collections import OrderedDict

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import content_disposition, request

from odoo.addons.portal.controllers.portal import pager as portal_pager

from .l10n_ec_portal_common_electronic import PortalElectronicCommon


class PortalRetention(PortalElectronicCommon):
    field_document_number = "number"

    def _get_l10n_ec_withhold_domain(self):
        # partner = request.env.user.partner_id
        domain = [
            ("type", "=", "purchase"),
            ("l10n_ec_xml_data_id.state", "=", "authorized"),
            # ("partner_id", "child_of", [partner.commercial_partner_id.id]),
            ("state", "=", "done"),
        ]
        return domain

    def _prepare_portal_layout_values(self):
        values = super(PortalRetention, self)._prepare_portal_layout_values()
        withhold_count = request.env["l10n_ec.withhold"].search_count(self._get_l10n_ec_withhold_domain())
        values["withhold_count"] = withhold_count
        return values

    # ------------------------------------------------------------
    # Retenciones
    # ------------------------------------------------------------

    def _withhold_get_page_view_values(self, withhold, access_token, **kwargs):
        values = {
            "page_name": "withhold",
            "withhold": withhold,
        }
        return self._get_page_view_values(
            withhold,
            access_token,
            values,
            "l10n_ec_my_withhold_history",
            False,
            **kwargs,
        )

    @http.route(
        ["/my/retencion", "/my/retencion/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_retencion(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        filterby=None,
        search=None,
        search_in=None,
        **kw,
    ):
        values = self._prepare_portal_layout_values()
        AccountRetention = request.env["l10n_ec.withhold"]
        domain = self._get_l10n_ec_withhold_domain()
        searchbar_sortings = self.get_searchbar_sortings()
        searchbar_inputs = self.get_searchbar_inputs()
        # default search
        if not search_in:
            search_in = "all"
        # search
        errors, error_message = self.search_validate(search_in, search)
        if not errors:
            search_domain = self.get_search_domain(search, search_in)
            domain += search_domain
        # default sort by order
        if not sortby:
            sortby = "fecha_auth"
        order = searchbar_sortings[sortby]["order"]
        # default filter by value
        if not filterby:
            filterby = "all"
        archive_groups = []
        if not errors:
            archive_groups = self._get_archive_groups(
                "l10n_ec.withhold",
                domain,
                fields=["number", "issue_date"],
                groupby="issue_date",
                order="issue_date desc",
            )
        if date_begin and date_end:
            domain += [
                ("issue_date", ">", date_begin),
                ("issue_date", "<=", date_end),
            ]

        # count for pager
        withhold_count = 0
        if not errors:
            withhold_count = AccountRetention.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/retencion",
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "filterby": filterby,
            },
            total=withhold_count,
            page=page,
            step=self._items_per_page,
        )
        # content according to pager and archive selected
        withholds = AccountRetention.browse()
        if not errors:
            withholds = AccountRetention.search(domain, order=order, limit=self._items_per_page, offset=pager["offset"])
        request.session["l10n_ec_my_withhold_history"] = withholds.ids[:100]
        values.update(
            {
                "errors": errors,
                "error_message": error_message,
                "date": date_begin,
                "withholds": withholds,
                "page_name": "withhold",
                "pager": pager,
                "archive_groups": archive_groups,
                "default_url": "/my/retencion",
                "searchbar_sortings": OrderedDict(sorted(searchbar_sortings.items())),
                "searchbar_inputs": OrderedDict(sorted(searchbar_inputs.items())),
                "sortby": sortby,
                "search_in": search_in,
                "search": search,
                "filterby": filterby,
            }
        )
        return request.render("l10n_ec_niif.portal_my_withhold", values)

    @http.route(["/my/retencion/<int:withhold_id>"], type="http", auth="public", website=True)
    def portal_my_withhold_detail(self, withhold_id, access_token=None, report_type=None, download=False, **kw):
        try:
            withhold_sudo = self._document_check_access("l10n_ec.withhold", withhold_id, access_token)
        except AccessError:
            return request.redirect("/my")

        if report_type == "xml" and download:
            attachment = withhold_sudo.l10n_ec_action_create_attachments_electronic()
            report = base64.decodebytes(attachment.datas).decode()
            reporthttpheaders = [
                ("Content-Type", "application/xml"),
                ("Content-Length", len(report)),
            ]
            filename = f"{withhold_sudo.get_printed_report_name_l10n_ec()}.xml"
            reporthttpheaders.append(("Content-Disposition", content_disposition(filename)))
            return request.make_response(report, headers=reporthttpheaders)
        elif report_type in ("html", "pdf", "text"):
            return self._show_report(
                model=withhold_sudo,
                report_type=report_type,
                report_ref="l10n_ec_niif.action_report_withhold",
                download=download,
            )

        values = self._withhold_get_page_view_values(withhold_sudo, access_token, **kw)
        return request.render("l10n_ec_niif.portal_withhold_page", values)
