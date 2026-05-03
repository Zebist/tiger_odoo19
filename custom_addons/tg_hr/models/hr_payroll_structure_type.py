# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollStructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'

    # 月度工作天数（用于日薪、缺勤、加班等基数）
    working_days_per_month = fields.Float(
        string="Working Days / Month",
        default=26.0,
        help="Standard number of working days per month, used as the base for daily wage, "
             "absence and overtime calculations.",
    )

    # 三大项拆分比例（占 wage 的比例，0~1）。BASIC 不需要字段，= 1 - 其他三项
    hra_pct = fields.Float(
        string="HRA %",
        digits=(5, 4),
        help="House Rent Allowance as a fraction of wage (e.g. 0.25 for 25%). "
             "Leave 0 to disable salary breakdown for this structure type.",
    )
    medical_pct = fields.Float(
        string="Medical %",
        digits=(5, 4),
        help="Medical Allowance as a fraction of wage (e.g. 0.15 for 15%).",
    )
    conveyance_pct = fields.Float(
        string="Conveyance %",
        digits=(5, 4),
        help="Conveyance Allowance as a fraction of wage (e.g. 0.10 for 10%).",
    )

    # 加班倍率
    ot_rate = fields.Float(
        string="OT Rate",
        default=2.0,
        help="Overtime multiplier applied to the hourly rate.",
    )

    # 缺勤基数：按 wage 还是按 basic 计算日薪
    absence_base = fields.Selection(
        [('wage', 'Wage'), ('basic', 'Basic')],
        string="Absence / Daily Wage Base",
        default='wage',
        help="Salary base used to compute daily wage (for absence deduction and daily-wage rules).",
    )

    # 迟到费率模式：按本人 wage 动态算 / 全员固定
    late_rate_mode = fields.Selection(
        [('wage_based', 'Wage Based'), ('fixed', 'Fixed Per-Minute Rate')],
        string="Late Rate Mode",
        default='wage_based',
        help="Wage Based: per-minute rate = wage / (working_days * hours_per_day * 60). "
             "Fixed: use the configured per-minute rate below.",
    )
    late_fixed_per_minute = fields.Float(
        string="Late Fixed Per-Minute Rate",
        digits=(12, 4),
        help="Fixed deduction per late minute, used when Late Rate Mode is 'Fixed'.",
    )

    @api.constrains('hra_pct', 'medical_pct', 'conveyance_pct')
    def _check_breakdown_pct(self):
        for rec in self:
            for f in ('hra_pct', 'medical_pct', 'conveyance_pct'):
                v = rec[f]
                if v < 0 or v > 1:
                    raise ValidationError(_(
                        "Breakdown percentages must be between 0 and 1 (got %(val)s for %(field)s).",
                        val=v, field=f,
                    ))
            total = rec.hra_pct + rec.medical_pct + rec.conveyance_pct
            if total > 1:
                raise ValidationError(_(
                    "HRA + Medical + Conveyance percentages cannot exceed 100%% (got %.2f%%).",
                    total * 100,
                ))
