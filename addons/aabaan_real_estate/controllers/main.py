# -*- coding: utf-8 -*-
"""Portal integration: the listing feed going out, and enquiries coming in.

* GET  /re/feed/<portal>.xml       published, available units for one portal
                                    (bayut, propertyfinder, dubizzle)
* GET  /re/photo/<unit>/<n>        a published unit's n-th photo (0 = cover)
* POST /re/lead/<token>            an enquiry, as JSON or form data, from a
                                    portal webhook, Zapier or a web form

The XML uses the common fields every UAE portal asks for (reference, permit,
type, beds, baths, size, price, location, photos, agent). Each portal's own
field names are mapped when the account is connected.
"""
import json
import logging
from xml.sax.saxutils import escape

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)
PORTAL_FIELDS = {
    'bayut': 'publish_bayut',
    'propertyfinder': 'publish_propertyfinder',
    'dubizzle': 'publish_dubizzle',
}


def _x(tag, value):
    if value in (False, None, ''):
        return '<%s/>' % tag
    return '<%s>%s</%s>' % (tag, escape(str(value)), tag)


class RealEstatePortal(http.Controller):

    @http.route('/re/feed/<string:portal>.xml', type='http', auth='public', csrf=False)
    def feed(self, portal, **kw):
        field = PORTAL_FIELDS.get(portal)
        if not field:
            return request.not_found()
        units = request.env['re.unit'].sudo().search([(field, '=', True), ('state', '=', 'available')])
        base = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        out = ['<?xml version="1.0" encoding="UTF-8"?>', '<list last_update="%s" listing_count="%d">' % (
            max(units.mapped('write_date')).strftime('%Y-%m-%d %H:%M:%S') if units else '', len(units))]
        for u in units:
            photos = []
            if u.image or u.project_id.image:
                photos.append('%s/re/photo/%d/0' % (base, u.id))
            photos += ['%s/re/photo/%d/%d' % (base, u.id, i + 1) for i in range(len(u.gallery_ids))]
            out.append('<property last_update="%s">' % u.write_date.strftime('%Y-%m-%d %H:%M:%S'))
            out += [
                _x('reference_number', u.reference),
                _x('permit_number', u.permit_number),
                _x('offering_type', 'RS' if u.purpose == 'sale' else 'RR'),
                _x('property_type', u.unit_type),
                _x('price', int(u.price or 0)),
                _x('currency', u.currency_id.name),
                _x('city', dict(u.project_id._fields['emirate'].selection).get(u.emirate)),
                _x('community', u.community),
                _x('sub_community', u.project_id.name),
                _x('property_name', u.project_id.name),
                _x('title_en', u.listing_title or '%s %s in %s' % (u.beds_label or '', dict(
                    u._fields['unit_type'].selection).get(u.unit_type), u.project_id.name or '')),
                _x('description_en', u.listing_description or ''),
                _x('bedroom', 'studio' if u.unit_type == 'studio' else u.bedrooms),
                _x('bathroom', u.bathrooms),
                _x('size', u.size_sqft),
                _x('completion_status', 'off_plan' if u.project_status == 'offplan' else 'completed'),
                _x('developer', u.developer_id.name),
                _x('view', u.view),
                _x('floor', u.floor),
            ]
            out.append('<agent>%s%s%s</agent>' % (
                _x('name', u.agent_id.name), _x('email', u.agent_id.email),
                _x('phone', u.agent_id.partner_id.phone)))
            out.append('<photo>%s</photo>' % ''.join(_x('url', p) for p in photos))
            out.append('</property>')
        out.append('</list>')
        return request.make_response('\n'.join(out), headers=[('Content-Type', 'application/xml; charset=utf-8')])

    @http.route('/re/photo/<int:unit_id>/<int:n>', type='http', auth='public')
    def photo(self, unit_id, n, **kw):
        unit = request.env['re.unit'].sudo().browse(unit_id).exists()
        if not unit or not unit.published:
            return request.not_found()
        if n == 0:
            record, field = (unit, 'image') if unit.image else (unit.project_id, 'image')
        else:
            gallery = unit.gallery_ids.sorted('sequence')
            if n > len(gallery):
                return request.not_found()
            record, field = gallery[n - 1], 'image'
        return request.env['ir.binary']._get_image_stream_from(record, field).get_response()

    @http.route('/re/lead/<string:token>', type='http', auth='public', methods=['POST'], csrf=False)
    def lead(self, token, **post):
        ICP = request.env['ir.config_parameter'].sudo()
        if not token or token != ICP.get_param('aabaan_real_estate.lead_token'):
            return request.make_response('forbidden', status=403)
        data = dict(post)
        if request.httprequest.mimetype == 'application/json':
            try:
                data.update(json.loads(request.httprequest.get_data(as_text=True) or '{}'))
            except ValueError:
                return request.make_response('invalid json', status=400)
        lead = request.env['crm.lead'].sudo()._re_from_portal(data)
        return request.make_response(json.dumps({'id': lead.id}),
                                     headers=[('Content-Type', 'application/json')])
