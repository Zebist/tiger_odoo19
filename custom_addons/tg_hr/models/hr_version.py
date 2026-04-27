# -*- coding: utf-8 -*-
from odoo import fields, models


_EXPAT_ALLOWANCE_TYPE = [('monthly', 'Monthly'), ('annual', 'Annual')]


class HrVersion(models.Model):
    _inherit = 'hr.version'

    expat_allowance = fields.Float(string='Expat Allowance', tracking=True)
    expat_allowance_type = fields.Selection(
        _EXPAT_ALLOWANCE_TYPE, string='Allowance Period', default='monthly', tracking=True,
    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    expat_allowance = fields.Float(
        related='version_id.expat_allowance',
        readonly=False,
        inherited=True,
    )
    expat_allowance_type = fields.Selection(
        _EXPAT_ALLOWANCE_TYPE,
        related='version_id.expat_allowance_type',
        readonly=False,
        inherited=True,
    )
