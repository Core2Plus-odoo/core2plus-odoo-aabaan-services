# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Products already sold on confirmed contracts are contract products;
    marking them re-derives the stream of every invoice that carries them."""
    env['product.template']._fm_cc_mark_contract_products()
