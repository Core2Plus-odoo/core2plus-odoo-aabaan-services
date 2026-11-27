# -*- coding: utf-8 -*-
"""The budget was first seeded one line per cost group (xmlids budget_*);
it is now one line per category (xmlids bl_*), loaded by this upgrade.
Drop the cost-group lines so the two do not add up twice. They were
loaded on 27 Nov 2026 and nobody has entered a budget by hand before
that, so only records still carrying the old xmlids go."""


def migrate(cr, version):
    cr.execute("""
        SELECT res_id FROM ir_model_data
         WHERE module = 'fm_command_centre' AND model = 'fm.cc.budget'
           AND name LIKE 'budget\\_%%'
    """)
    ids = [r[0] for r in cr.fetchall()]
    if ids:
        cr.execute("DELETE FROM fm_cc_budget WHERE id IN %s", (tuple(ids),))
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'fm_command_centre' AND model = 'fm.cc.budget'
           AND name LIKE 'budget\\_%%'
    """)
