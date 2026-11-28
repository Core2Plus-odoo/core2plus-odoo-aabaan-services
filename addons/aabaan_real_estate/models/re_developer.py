# -*- coding: utf-8 -*-
from odoo import fields, models


class ReDeveloper(models.Model):
    _name = 're.developer'
    _description = 'Property Developer'
    _order = 'name'

    name = fields.Char(required=True)
    logo = fields.Image(max_width=512, max_height=512)
    website = fields.Char()
    project_ids = fields.One2many('re.project', 'developer_id')
    project_count = fields.Integer(compute='_compute_project_count')
    active = fields.Boolean(default=True)

    def _compute_project_count(self):
        for dev in self:
            dev.project_count = len(dev.project_ids)
