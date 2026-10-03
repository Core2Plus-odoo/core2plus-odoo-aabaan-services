# Tools

Standalone scripts. **Not Odoo addons** — nothing here has a
`__manifest__.py`, so Odoo never loads this directory. They run from a
laptop or a webshell against a live instance over XML-RPC.

## `fta_archive.py` — FTA record-retention archive

Extracts issued tax invoices and their supporting data from an Odoo
instance into a self-contained archive on disk, so the records survive the
instance being decommissioned. Written for the legacy instance's ~2,600
invoices ahead of its Oct 2026 retirement.

### Run it

```bash
export ODOO_URL=https://<instance>.odoo.com
export ODOO_DB=<database>
export ODOO_LOGIN=<a read-only user, not admin>
export ODOO_API_KEY=<API key from Preferences → Account Security>

python3 tools/test_fta_archive.py                      # prove the guard works
python3 tools/fta_archive.py --out ./fta-archive --dry-run
python3 tools/fta_archive.py --out ./fta-archive --limit 20   # trial
python3 tools/fta_archive.py --out ./fta-archive               # full run
```

Re-running skips invoices already written, so an interrupted run resumes.

### Retention is 7 years, not 5

The "5 years" everyone quotes is the VAT floor and does not settle it. The
same invoice is also a Corporate Tax record, and Federal Decree-Law
47/2022 art. 56 requires **7 years** from the end of the relevant tax
period. A 5-year archive would under-retain. The archive stamps 7 years,
and the period extends automatically while an audit, dispute or voluntary
disclosure is open — it is a floor, not a delete-by date.

### Why it never renders a PDF

Odoo's `_render_qweb_pdf` creates an `ir.attachment` whenever the report
carries a "Save as Attachment Prefix". On a database that must never be
written to, rendering 2,600 invoices could mean 2,600 new rows. So the
script never renders. It takes:

1. **The PDF as issued** — since Odoo 17 this is stored on the invoice in
   `invoice_pdf_report_file`. This is the legally correct document: the
   exact bytes the customer received, not a re-render with today's
   template and company details.
2. **Attached PDFs** — signed copies, LPOs, proof of completion that
   someone attached to the invoice.

Both are pure reads. Invoices with neither are exported as structured data
and **counted and reported**, so the gap is visible rather than silently
papered over.

> A trap worth knowing: Odoo hides field-attachments (those with
> `res_field` set) from ordinary `ir.attachment` searches. A search for
> invoice PDFs that doesn't account for this returns nothing and produces
> an archive with no PDFs in it, with no error. That is why the issued PDF
> is read from the invoice field directly.

### Read-only by construction

Every call goes through a whitelist of non-mutating methods. `create`,
`write`, `unlink`, `copy`, `_render_qweb_pdf` and everything else raise
**before the request reaches the network** — the guarantee is that nothing
is sent, not that the server happened to refuse it. `test_fta_archive.py`
asserts exactly that, and should be run before every use.

**Two writes no script can prevent, disclosed rather than glossed:**
logging in inserts a `res.users.log` row, and reading a stored computed
field that is stale can flush an `UPDATE`. Neither alters an invoice. Take
a tripwire either side of the run and hand the client the diff:

```sql
SELECT max(id), count(*) FROM ir_attachment;
SELECT max(id), count(*) FROM mail_message;
```

### On Rule 3

`CLAUDE.md` Rule 3 makes the legacy database read-only forever and requires
scripts to assert they are not targeting it. This script's entire purpose
is to read that instance, so it cannot make that assertion. It enforces the
underlying intent more strongly instead — a method whitelist is a stronger
guarantee than an assertion about which database you are pointed at.

**This is a deliberate, narrow exception and should be confirmed before the
first real run.** It exists because the retention obligation is a
regulator's, not ours, and the records have to come out before the
instance goes away.

### What this archive is not

It covers **issued customer invoices and credit notes only**. The retention
obligation is broader: purchase invoices and input-tax documents, contracts
and quotations, proof that the service was actually delivered, payment
records, credit and debit notes, and filed VAT returns with their workings.
Scoping the job to "2,621 invoices" understates it — the invoices are the
part that disappears with the instance, which is why they come first.
