# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
"""Shared print helpers for the letterhead reports.

Plain functions rather than a mixin: the report models keep thin,
identically-named wrapper methods (QWeb calls them on the record), and the
logic lives once here.
"""


def line_desc(line):
    """Line description without the internal product code prefix —
    '[AAB-CLN-DEEP-2BR] Deep Cleaning — 2BR' prints as the name only."""
    name = (line.name or '').strip()
    code = line.product_id.default_code
    if code and name.startswith('[%s]' % code):
        name = name[len(code) + 2:].lstrip()
    return name


def amount_in_words(record):
    """Grand total in words, or '' when the currency cannot spell it —
    a report must never crash over a wording nicety."""
    try:
        return record.currency_id.amount_to_text(record.amount_total)
    except Exception:
        return ''
