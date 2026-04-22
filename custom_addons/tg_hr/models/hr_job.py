# -*- coding: utf-8 -*-

from odoo import fields, models


class HrJob(models.Model):
    _inherit = "hr.job"

    is_manager = fields.Boolean(string="Is Manager", default=False)

