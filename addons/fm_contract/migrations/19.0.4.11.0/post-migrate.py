# -*- coding: utf-8 -*-
"""Total Contract Value is now the order total incl. VAT.

A stored compute whose formula changed is not recomputed on upgrade by
itself, so every existing order still holds the old ACV × term figure.
One SQL statement sets it to amount_total, which is exactly what the new
compute would write."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE sale_order
           SET fm_tcv = amount_total
         WHERE fm_tcv IS DISTINCT FROM amount_total
    """)
