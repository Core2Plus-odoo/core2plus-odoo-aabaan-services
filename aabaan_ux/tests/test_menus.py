# Part of the Aabaan Odoo build by C2P Consultants FZC LLC.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMenuArchitecture(TransactionCase):

    def test_contracts_section_owns_the_daily_menus(self):
        section = self.env.ref('aabaan_ux.menu_sale_contracts_section')
        for xmlid in ('aabaan_contract_cockpit.menu_contract_register',
                      'aabaan_templates_library.menu_templates_library'):
            self.assertEqual(
                self.env.ref(xmlid).parent_id, section,
                "%s must sit under Sales › Contracts" % xmlid)

    def test_setup_section_owns_the_config_menus(self):
        setup = self.env.ref('aabaan_ux.menu_sale_aabaan_setup')
        for xmlid in ('aabaan_service_contracts.menu_service_tags',
                      'aabaan_pricing_guard.menu_zero_price_products'):
            self.assertEqual(
                self.env.ref(xmlid).parent_id, setup,
                "%s must sit under Sales › Aabaan Setup" % xmlid)

    def test_nothing_was_deleted_or_detached(self):
        """Reorganise, never remove: every menu still exists, still has its
        action, and still lives under the Sales root."""
        root = self.env.ref('sale.sale_menu_root')
        for xmlid in ('aabaan_contract_cockpit.menu_contract_register',
                      'aabaan_templates_library.menu_templates_library',
                      'aabaan_service_contracts.menu_service_tags',
                      'aabaan_pricing_guard.menu_zero_price_products'):
            menu = self.env.ref(xmlid)
            self.assertTrue(menu.action, "%s lost its action" % xmlid)
            self.assertEqual(menu.parent_id.parent_id, root,
                             "%s left the Sales app" % xmlid)
