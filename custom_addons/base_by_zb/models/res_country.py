# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCountry(models.Model):
    _inherit = 'res.country'

    dial_code = fields.Char(
        string='Dial Code',
        compute='_compute_dial_code',
        store=True,
        help="International dialing prefix derived from phone_code, e.g. +880",
    )

    @api.depends('phone_code')
    def _compute_dial_code(self):
        for rec in self:
            rec.dial_code = f'+{rec.phone_code}' if rec.phone_code else ''
