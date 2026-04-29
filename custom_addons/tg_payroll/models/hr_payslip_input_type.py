# -*- coding: utf-8 -*-
from odoo import fields, models


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    # 单位标记，仅用于展示和业务校验，不参与计算
    unit = fields.Selection(
        [
            ('amount', 'Amount'),
            ('day', 'Day'),
            ('hour', 'Hour'),
            ('percent', 'Percent'),
        ],
        string="Unit",
        default='amount',
        help="Unit of measure for this input. For information / display only; "
             "salary rules read the raw amount value.",
    )
