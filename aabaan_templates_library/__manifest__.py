# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
{
    'name': 'Aabaan Templates Library',
    'version': '19.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Card gallery for quotation templates (approved UI screens)',
    'description': """
The Templates Library screen from the approved UI set, standard-first: no
new models — native sale.order.template gets two computed counters (lines
on the template, quotations created from it) and a kanban card gallery,
reachable from Sales > Templates Library. Creating, editing and using
templates stays fully native.
""",
    'author': 'C2P Consultants FZC LLC',
    'license': 'OPL-1',
    'depends': ['sale_management'],
    'data': [
        'views/template_views.xml',
    ],
    'installable': True,
    'application': False,
}
