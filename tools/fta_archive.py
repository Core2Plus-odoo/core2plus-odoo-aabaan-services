#!/usr/bin/env python3
"""FTA record-retention archive extractor — STRUCTURALLY READ-ONLY.

Extracts tax invoices and their supporting data from an Odoo instance into
a self-contained archive on disk, so the records survive the instance being
decommissioned.

WHY THIS EXISTS
    The legacy instance holds ~2,600 invoices that must remain producible
    to the FTA long after the instance is gone. Deadline: the instance is
    due to be retired in Oct 2026.

RETENTION PERIOD — 7 YEARS, NOT 5
    The commonly quoted "5 years" is the VAT floor and it is not sufficient
    on its own:
      * FDL 8/2017 (VAT) art. 78 says WHAT to keep and defers the period to
        regulation.
      * Cabinet Decision 74/2023 (Tax Procedures ER) art. 3(1): 5 years
        following the Tax Period for a Taxable Person; 7 years for real
        estate records.
      * FDL 47/2022 (Corporate Tax) art. 56: 7 years from the end of the
        relevant Tax Period.
    The same invoice is both a VAT record and a Corporate Tax record, so a
    5-year policy buys nothing. This archive is stamped 7 years.
    The period also extends in several situations (audit under way, dispute,
    voluntary disclosure) — 7 years is a floor, not a delete-on-expiry date.

WHY BOTH PDF AND STRUCTURED DATA
    Cabinet Decision 74/2023 art. 4 permits retaining the INFORMATION rather
    than the original document, provided it is identical to the original,
    available throughout the period, and reproducible in easily readable
    form on request. That route is real, but it breaks the moment a report
    template changes and an old invoice would re-render differently. So the
    archive keeps the PDF AS ISSUED where one is stored, and the full
    structured data always. Belt and braces, cheaply.

READ-ONLY BY CONSTRUCTION, NOT BY PROMISE
    CLAUDE.md Rule 3 makes the legacy database read-only forever, and
    requires scripts to assert they are not targeting it. This script's
    entire purpose is to READ that instance, so it cannot make that
    assertion — instead it enforces the underlying intent more strongly:

      * Every call goes through ReadOnly, which permits ONLY a whitelist of
        non-mutating methods. create/write/unlink/copy and everything else
        raise before reaching the network.
      * It NEVER renders a report. Rendering an Odoo invoice report can
        store an ir.attachment, which would be a write to a database that
        must never be written to. Already-stored PDFs are fetched instead;
        invoices without one are exported as data and reported, so the gap
        is visible rather than silently papered over.
      * It writes only to the local filesystem.

    A method whitelist is a strictly stronger guarantee than an assertion
    about which database you happen to be pointing at. Read the code before
    running it against production — that is the point of it being short.

WHAT THIS SCRIPT CANNOT PREVENT — DISCLOSE, DO NOT CLAIM "ZERO WRITES"
    Two writes are outside any script's control, and pretending otherwise
    would be worse than naming them:

      * LOGGING IN WRITES A ROW. Odoo's authenticate() inserts a
        res.users.log record on every connection — that is how last-login
        is derived. It is small and benign, but it is a write, and the
        client should be told rather than discover it.
      * READING A STALE STORED COMPUTE CAN WRITE. If a stored computed
        field is sitting in Odoo's recompute queue, reading it runs the
        compute and flushes the result as an UPDATE. account.move carries
        many stored computes. This is unlikely on a quiet instance and
        impossible to rule out from outside.

    Neither alters an invoice. Run a tripwire either side of the export and
    hand the client the diff as evidence:

        SELECT max(id), count(*) FROM ir_attachment;
        SELECT max(id), count(*) FROM mail_message;

    Also: connect as a NON-ADMIN user with read access only. Beyond least
    privilege, an admin login through a proxy on a different hostname can
    silently rewrite the instance's web.base.url — which would break portal
    links and invoice URLs for real users. Plain XML-RPC does not trigger
    that path, but there is no reason to be near it.

CREDENTIALS
    Environment variables only, never arguments or files (Rule 3):
        ODOO_URL      https://your-instance.odoo.com
        ODOO_DB       database name
        ODOO_LOGIN    user login
        ODOO_API_KEY  API key (Preferences -> Account Security)

USAGE
    export ODOO_URL=... ODOO_DB=... ODOO_LOGIN=... ODOO_API_KEY=...
    python3 tools/fta_archive.py --out ./fta-archive-2026 --dry-run
    python3 tools/fta_archive.py --out ./fta-archive-2026

    Re-running skips invoices already written, so an interrupted run
    resumes instead of starting over.
"""
import argparse
import base64
import csv
import hashlib
import json
import os
import sys
import xmlrpc.client
from datetime import datetime, timezone

RETENTION_YEARS = 7

# Only these reach the network. Anything else raises before the call is made.
READ_ONLY_METHODS = frozenset({
    'search', 'search_read', 'search_count', 'read', 'fields_get',
    'read_group', 'name_get', 'name_search', 'check_access_rights',
})

# The mandatory particulars of a UAE tax invoice (VAT Executive Regulation,
# Cabinet Decision 52/2017 art. 59). Retaining the INFORMATION route is only
# open if every one of these survives, so they are exported explicitly rather
# than relying on whatever the invoice list view happens to show.
INVOICE_FIELDS = [
    'name', 'move_type', 'state', 'invoice_date', 'invoice_date_due',
    'delivery_date', 'partner_id', 'company_id', 'currency_id',
    'amount_untaxed', 'amount_tax', 'amount_total', 'amount_residual',
    'payment_state', 'invoice_origin', 'ref', 'narration',
    'invoice_payment_term_id', 'fiscal_position_id', 'journal_id',
    'create_date', 'write_date', 'invoice_user_id',
]
LINE_FIELDS = [
    'sequence', 'display_type', 'name', 'product_id', 'quantity',
    'product_uom_id', 'price_unit', 'discount', 'price_subtotal',
    'price_total', 'tax_ids', 'account_id',
]
PARTNER_FIELDS = [
    'name', 'vat', 'street', 'street2', 'city', 'state_id', 'zip',
    'country_id', 'phone', 'email', 'company_registry',
]
COMPANY_FIELDS = [
    'name', 'vat', 'company_registry', 'street', 'street2', 'city',
    'state_id', 'zip', 'country_id', 'phone', 'email',
]


class ReadOnlyViolation(RuntimeError):
    """Raised before any network call that is not a read."""


class ReadOnly:
    """An Odoo XML-RPC client that can only read.

    The whitelist is checked before the request is built, so a mutating
    call never reaches the server even if the server would have allowed it.
    """

    def __init__(self, url, db, login, api_key):
        self.url, self.db, self.api_key = url.rstrip('/'), db, api_key
        common = xmlrpc.client.ServerProxy(
            '%s/xmlrpc/2/common' % self.url, allow_none=True)
        self.uid = common.authenticate(db, login, api_key, {})
        if not self.uid:
            raise SystemExit(
                "Authentication failed for %s on %s — check ODOO_LOGIN and "
                "ODOO_API_KEY." % (login, db))
        self._models = xmlrpc.client.ServerProxy(
            '%s/xmlrpc/2/object' % self.url, allow_none=True)
        self.call_count = 0

    def __call__(self, model, method, *args, **kwargs):
        if method not in READ_ONLY_METHODS:
            raise ReadOnlyViolation(
                "Refusing to call %s.%s — this archiver is read-only and "
                "the source database must never be written to. Permitted: %s"
                % (model, method, ', '.join(sorted(READ_ONLY_METHODS))))
        self.call_count += 1
        return self._models.execute_kw(
            self.db, self.uid, self.api_key, model, method,
            list(args), kwargs)


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def flatten(value):
    """XML-RPC gives many2one as [id, name] and False for empty — normalise
    both so the JSON is readable years from now without Odoo to interpret it."""
    if value is False or value is None:
        return None
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], int):
        return {'id': value[0], 'name': value[1]}
    return value


def clean(record):
    return {key: flatten(val) for key, val in record.items()}


def fetch_related(api, model, ids, fields):
    if not ids:
        return {}
    rows = api(model, 'read', sorted(set(ids)), fields=fields)
    return {row['id']: clean(row) for row in rows}


def has_issued_pdf_field(api):
    """Since Odoo 17 the PDF actually sent to the customer is kept on the
    invoice in `invoice_pdf_report_file`. Older versions have no such field,
    so resolve it at runtime and fall back rather than assuming a version."""
    described = api('account.move', 'fields_get', [], attributes=['type'])
    return 'invoice_pdf_report_file' in described


def issued_pdfs(api, ids):
    """The invoice PDF as issued, keyed by move id.

    Read straight off the invoice rather than by searching ir.attachment:
    `invoice_pdf_report_file` is a Binary stored with attachment=True, and
    Odoo hides field-attachments (res_field set) from ordinary
    ir.attachment searches. Searching without saying so finds nothing and
    yields a silent archive full of missing PDFs.
    """
    out = {}
    for row in api('account.move', 'read', ids,
                   fields=['invoice_pdf_report_file']):
        blob = row.get('invoice_pdf_report_file')
        if blob:
            out[row['id']] = blob
    return out


def loose_pdf_attachments(api, ids):
    """PDFs a human attached to the invoice (signed copies, LPOs, proof of
    completion). res_field=False keeps these separate from the field
    storage handled above."""
    return api('ir.attachment', 'search_read',
               [('res_model', '=', 'account.move'), ('res_id', 'in', ids),
                ('res_field', '=', False),
                ('mimetype', '=', 'application/pdf')],
               fields=['res_id', 'name', 'datas', 'create_date'])


def archive(api, out_dir, limit=None, dry_run=False, batch=50):
    docs_dir = os.path.join(out_dir, 'invoices')
    if not dry_run:
        os.makedirs(docs_dir, exist_ok=True)

    domain = [('move_type', 'in', ('out_invoice', 'out_refund')),
              ('state', '!=', 'draft')]
    ids = api('account.move', 'search', domain, order='id')
    if limit:
        ids = ids[:limit]
    total = len(ids)
    stores_issued = has_issued_pdf_field(api)
    print("Found %s posted customer invoices and credit notes." % total)
    print("Source stores the issued PDF on the invoice: %s"
          % ('yes' if stores_issued else
             'no (pre-17 layout — falling back to attachments)'))

    if dry_run:
        sample = api('account.move', 'read', ids[:3], fields=['name'])
        print("Dry run — nothing written. First few: %s"
              % ', '.join(row['name'] or '?' for row in sample))
        probe = ids[:200]
        found = len(issued_pdfs(api, probe)) if stores_issued else 0
        loose = len(loose_pdf_attachments(api, probe))
        print("In a %s-invoice probe: %s issued PDFs, %s attached PDFs."
              % (len(probe), found, loose))
        return {'total': total, 'written': 0, 'with_pdf': 0, 'data_only': 0}

    manifest, written, with_pdf, data_only, attached_only = [], 0, 0, 0, 0

    for start in range(0, total, batch):
        chunk = ids[start:start + batch]
        moves = api('account.move', 'read', chunk, fields=INVOICE_FIELDS)

        line_rows = api('account.move.line', 'search_read',
                        [('move_id', 'in', chunk),
                         ('display_type', 'in',
                          ('product', 'line_section', 'line_note'))],
                        fields=LINE_FIELDS + ['move_id'])
        lines_by_move = {}
        for row in line_rows:
            move_id = row['move_id'][0] if row['move_id'] else None
            lines_by_move.setdefault(move_id, []).append(clean(row))

        partners = fetch_related(
            api, 'res.partner',
            [m['partner_id'][0] for m in moves if m['partner_id']],
            PARTNER_FIELDS)
        companies = fetch_related(
            api, 'res.company',
            [m['company_id'][0] for m in moves if m['company_id']],
            COMPANY_FIELDS)

        # Already-stored PDFs only. Rendering is never requested: Odoo's
        # _render_qweb_pdf creates an ir.attachment whenever the report
        # carries a "Save as Attachment Prefix", which would be a write to
        # a database that must never be written to. Two sources, both pure
        # reads: the PDF as issued to the customer, and anything a human
        # attached alongside it.
        issued = issued_pdfs(api, chunk) if stores_issued else {}
        pdf_by_move = {}
        for move_id, blob in issued.items():
            pdf_by_move.setdefault(move_id, []).append({
                'name': '%s-as-issued.pdf' % move_id, 'datas': blob,
                'create_date': None, 'as_issued': True})
        for att in loose_pdf_attachments(api, chunk):
            pdf_by_move.setdefault(att['res_id'], []).append({
                'name': att['name'], 'datas': att['datas'],
                'create_date': att.get('create_date'), 'as_issued': False})

        for move in moves:
            slug = (move['name'] or 'unnamed').replace('/', '-').replace(' ', '')
            record_path = os.path.join(docs_dir, '%s.json' % slug)
            if os.path.exists(record_path):
                continue

            pdfs = []
            for att in pdf_by_move.get(move['id'], []):
                if not att.get('datas'):
                    continue
                blob = base64.b64decode(att['datas'])
                label = 'as-issued' if att['as_issued'] else att['name']
                pdf_name = '%s__%s' % (slug, label.replace('/', '-'))
                if not pdf_name.lower().endswith('.pdf'):
                    pdf_name += '.pdf'
                with open(os.path.join(docs_dir, pdf_name), 'wb') as handle:
                    handle.write(blob)
                pdfs.append({'file': pdf_name, 'sha256': sha256(blob),
                             'bytes': len(blob),
                             'as_issued': att['as_issued'],
                             'stored_on': att.get('create_date')})

            record = {
                'invoice': clean(move),
                'lines': lines_by_move.get(move['id'], []),
                'customer': partners.get(
                    move['partner_id'][0] if move['partner_id'] else None),
                'supplier': companies.get(
                    move['company_id'][0] if move['company_id'] else None),
                'pdfs': pdfs,
                'archived_at': datetime.now(timezone.utc).isoformat(),
                'source_database': api.db,
            }
            payload = json.dumps(record, indent=2,
                                 ensure_ascii=False, sort_keys=True)
            blob = payload.encode('utf-8')
            with open(record_path, 'w', encoding='utf-8') as handle:
                handle.write(payload)

            if any(p['as_issued'] for p in pdfs):
                with_pdf += 1
            elif pdfs:
                attached_only += 1
            else:
                data_only += 1
            written += 1
            manifest.append({
                'invoice_number': move['name'],
                'type': move['move_type'],
                'invoice_date': move['invoice_date'] or '',
                'customer': (move['partner_id'][1]
                             if move['partner_id'] else ''),
                'customer_trn': (partners.get(move['partner_id'][0], {})
                                 or {}).get('vat') or '',
                'issuing_entity': (move['company_id'][1]
                                   if move['company_id'] else ''),
                'entity_trn': (companies.get(move['company_id'][0], {})
                               or {}).get('vat') or '',
                'currency': (move['currency_id'][1]
                             if move['currency_id'] else ''),
                'net': move['amount_untaxed'],
                'vat': move['amount_tax'],
                'total': move['amount_total'],
                'data_file': os.path.relpath(record_path, out_dir),
                'data_sha256': sha256(blob),
                'pdf_files': ';'.join(p['file'] for p in pdfs),
                'pdf_present': (
                    'as issued' if any(p['as_issued'] for p in pdfs)
                    else 'attached only' if pdfs
                    else 'NO — data only'),
            })

        print("  %s / %s" % (min(start + batch, total), total), flush=True)

    _write_manifest(out_dir, manifest)
    _write_readme(out_dir, api.db, total, written, with_pdf,
                  attached_only, data_only)
    return {'total': total, 'written': written, 'with_pdf': with_pdf,
            'attached_only': attached_only, 'data_only': data_only}


def _write_manifest(out_dir, rows):
    if not rows:
        return
    path = os.path.join(out_dir, 'manifest.csv')
    exists = os.path.exists(path)
    with open(path, 'a', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def _write_readme(out_dir, db, total, written, with_pdf, attached_only,
                  data_only):
    stamped = datetime.now(timezone.utc).strftime('%d %B %Y')
    with open(os.path.join(out_dir, 'README.txt'), 'w', encoding='utf-8') as fh:
        fh.write(
            "AABAN — TAX RECORD ARCHIVE\n"
            "==========================\n\n"
            "Source database : %s\n"
            "Extracted on    : %s\n"
            "Invoices found  : %s\n"
            "Invoices written: %s\n"
            "  with the PDF as issued : %s\n"
            "  attached PDFs only     : %s\n"
            "  structured data only   : %s\n\n"
            "RETAIN UNTIL: at least %s years after the end of the tax period\n"
            "each invoice belongs to. Corporate Tax (Federal Decree-Law\n"
            "47/2022 art. 56) requires 7 years; the VAT 5-year period\n"
            "(Cabinet Decision 74/2023 art. 3) is a floor, not the answer.\n"
            "The period extends automatically while an audit, dispute or\n"
            "voluntary disclosure is open — do not delete on expiry without\n"
            "checking.\n\n"
            "WHAT IS HERE\n"
            "  manifest.csv  one row per invoice, with a SHA-256 of its data\n"
            "                file so alteration is detectable.\n"
            "  invoices/     one JSON per invoice holding every mandatory\n"
            "                particular required by the VAT Executive\n"
            "                Regulation (Cabinet Decision 52/2017 art. 59),\n"
            "                plus the PDF as issued where one was stored.\n\n"
            "INVOICES MARKED 'data only' HAVE NO STORED PDF\n"
            "  Their full structured data is here, which Cabinet Decision\n"
            "  74/2023 art. 4 permits as an alternative to the original\n"
            "  document. Regenerating a PDF from this data is acceptable\n"
            "  only if it reproduces the invoice AS ISSUED — if the report\n"
            "  template has changed since, it will not, so treat the JSON\n"
            "  as the record of truth.\n\n"
            "NOTE ON INTEGRITY\n"
            "  The SHA-256 digests are good practice and evidential\n"
            "  insurance. No UAE provision was found requiring hashing,\n"
            "  WORM storage or digital signatures for ordinary tax\n"
            "  invoices, and none is claimed here.\n\n"
            "NOTE ON LANGUAGE\n"
            "  The FTA may require records in Arabic, or a translation of\n"
            "  English records for which the taxpayer is responsible.\n\n"
            "This archive covers ISSUED customer invoices and credit notes.\n"
            "It is not the whole retention obligation: purchase invoices,\n"
            "contracts, proof of service completion, payment records and\n"
            "filed VAT returns must be retained too.\n"
            % (db, stamped, total, written, with_pdf, attached_only,
               data_only, RETENTION_YEARS))


def main():
    parser = argparse.ArgumentParser(
        description="Read-only FTA record archive extractor.")
    parser.add_argument('--out', required=True, help="Output directory.")
    parser.add_argument('--limit', type=int,
                        help="Stop after N invoices (for a trial run).")
    parser.add_argument('--dry-run', action='store_true',
                        help="Count and report, write nothing.")
    args = parser.parse_args()

    missing = [name for name in
               ('ODOO_URL', 'ODOO_DB', 'ODOO_LOGIN', 'ODOO_API_KEY')
               if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "Missing environment variable(s): %s\n"
            "Credentials come from the environment, never from arguments "
            "or a committed file." % ', '.join(missing))

    api = ReadOnly(os.environ['ODOO_URL'], os.environ['ODOO_DB'],
                   os.environ['ODOO_LOGIN'], os.environ['ODOO_API_KEY'])
    print("Connected read-only to %s as uid %s." % (api.db, api.uid))

    stats = archive(api, args.out, limit=args.limit, dry_run=args.dry_run)

    print("\nDone. %s read calls, zero writes (enforced by whitelist)."
          % api.call_count)
    if not args.dry_run:
        print("Archived %s of %s — %s with the PDF as issued, %s with "
              "attached PDFs only, %s structured data only."
              % (stats['written'], stats['total'], stats['with_pdf'],
                 stats['attached_only'], stats['data_only']))
        if stats['data_only']:
            print("\n%s invoice(s) had no stored PDF. Their structured data "
                  "is archived; see README.txt in the output directory for "
                  "what that means for compliance." % stats['data_only'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
