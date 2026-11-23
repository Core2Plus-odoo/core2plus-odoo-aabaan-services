# -*- coding: utf-8 -*-
"""A contract made by Create Contract carries its quotation's SO number.

Contracts created before this version got a fresh number from the sequence;
give them the quotation's number back.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE sale_order c
           SET name = q.name
          FROM sale_order q
         WHERE c.fm_source_quotation_id = q.id
           AND c.name IS DISTINCT FROM q.name
     RETURNING c.id
    """)
