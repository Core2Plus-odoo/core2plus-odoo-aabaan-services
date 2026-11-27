import logging

_logger = logging.getLogger(__name__)

# Trading name and address per branch, as Aaban sent them for their Tax
# Invoices (27 Nov 2026). Matched on the branch name; only a branch with no
# invoice name yet is filled, so an edit made in the form is never undone.
BRANCH_INVOICE_DETAILS = {
    "ajman": ("Aaban Classic Building Cleaning LLC",
              "Shop no 1, Jurf Ajman"),
    "dubai": ("Aaban Classic Building Cleaning",
              "Office no 126, Bin Saloom Building, Hor Al Anz, Diera, Dubai"),
    "sharjah": ("Aaban Classic Building Cleaning SHJ BR-2",
                "Shop no 1 & 2, Al Sharq, Butena, Sharjah"),
    "fujairah": ("Aaban Classic Building Cleaning Fujairah Branch 1",
                 "Shop no 3, Sakamkam, Fujairah"),
}


def migrate(cr, version):
    for key, (name, street) in BRANCH_INVOICE_DETAILS.items():
        cr.execute("""
            UPDATE fm_branch
               SET invoice_name = %s, street = %s, city = NULL
             WHERE lower(name) LIKE %s
               AND (invoice_name IS NULL OR invoice_name = '')
        """, (name, street, "%%%s%%" % key))
        _logger.info("fm_branch: invoice details set on %s branch(es) matching %s",
                     cr.rowcount, key)
