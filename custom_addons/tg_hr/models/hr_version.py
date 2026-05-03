# -*- coding: utf-8 -*-
from odoo import api, fields, models

PAYROLL_GROUP = "hr_payroll.group_hr_payroll_user"


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # ---- 调整权限 ---------------------------------------------------------
    date_version = fields.Date(groups="hr.group_hr_user,tg_hr.group_tg_hr_version_readonly")

    # ---- 标准津贴字段（规则中按字段名稳定引用） ---------------------------
    kpi_base = fields.Monetary(
        string="KPI Base",
        groups=PAYROLL_GROUP,
        help="Base amount used to compute the monthly KPI bonus. "
             "Grade A pays 100%, B pays 50%, C pays 0%.",
    )
    phone_allowance = fields.Monetary(
        string="Phone Allowance (Full Month)",
        groups=PAYROLL_GROUP,
        help="Monthly phone allowance at full attendance. Pro-rated by attendance in payroll rules.",
    )
    perfect_attend_amount = fields.Monetary(
        string="Perfect Attendance Bonus",
        groups=PAYROLL_GROUP,
        help="Bonus paid when there is no absence in the period.",
    )
    expat_daily = fields.Monetary(
        string="Expat Allowance / Day",
        groups=PAYROLL_GROUP,
        help="Daily expatriate allowance, multiplied by the EXPAT input (days).",
    )
    trip_daily = fields.Monetary(
        string="Business Trip Allowance / Day",
        groups=PAYROLL_GROUP,
        help="Daily business trip allowance, multiplied by the TRIP input (days).",
    )
    housing_allowance = fields.Monetary(
        string="Housing Allowance",
        groups=PAYROLL_GROUP,
        help="Fixed monthly housing allowance.",
    )
    overtime = fields.Monetary(
        string="Overtime Rate / Hour",
        currency_field='currency_id',
        groups=PAYROLL_GROUP,
        help="Hourly overtime rate. Rule: OT_hours × overtime.",
    )

    @api.model
    def _get_whitelist_fields_from_template(self):
        # 让 Load a Template 也复制本模块加的津贴字段
        return super()._get_whitelist_fields_from_template() + [
            'kpi_base',
            'phone_allowance',
            'perfect_attend_amount',
            'expat_daily',
            'trip_daily',
            'housing_allowance',
            'overtime',
        ]

    # ---- 三大项拆分（compute store） ------------------------------------
    basic_amount = fields.Monetary(
        string="Basic",
        compute='_compute_salary_breakdown',
        store=True,
        groups=PAYROLL_GROUP,
    )
    hra_amount = fields.Monetary(
        string="House Rent Allowance",
        compute='_compute_salary_breakdown',
        store=True,
        groups=PAYROLL_GROUP,
    )
    medical_amount = fields.Monetary(
        string="Medical Allowance",
        compute='_compute_salary_breakdown',
        store=True,
        groups=PAYROLL_GROUP,
    )
    conveyance_amount = fields.Monetary(
        string="Conveyance Allowance",
        compute='_compute_salary_breakdown',
        store=True,
        groups=PAYROLL_GROUP,
    )

    # ---- 日薪展示（不存储） ----------------------------------------------
    daily_wage = fields.Monetary(
        string="Daily Wage",
        compute='_compute_daily_wage',
        groups=PAYROLL_GROUP,
        help="Display only. Computed as base / working_days_per_month, where the base is "
             "BASIC or WAGE depending on the structure type's Absence Base setting.",
    )

    @api.depends(
        'wage',
        'structure_type_id',
        'structure_type_id.hra_pct',
        'structure_type_id.medical_pct',
        'structure_type_id.conveyance_pct',
    )
    def _compute_salary_breakdown(self):
        for rec in self:
            basic, hra, med, conv = self._split_wage(rec.wage, rec.structure_type_id, rec.currency_id)
            rec.basic_amount = basic
            rec.hra_amount = hra
            rec.medical_amount = med
            rec.conveyance_amount = conv

    @api.model
    def _split_wage(self, wage, structure_type, currency):
        """按 structure type 的 HRA/Medical/Conveyance 比例拆分 wage。
        返回 (basic, hra, med, conv)。尾差归 BASIC，确保 TOTAL = WAGE。
        所有比例为 0 时不拆分：BASIC = wage，其余 = 0。"""
        wage = wage or 0.0
        hra_pct = structure_type.hra_pct if structure_type else 0.0
        med_pct = structure_type.medical_pct if structure_type else 0.0
        conv_pct = structure_type.conveyance_pct if structure_type else 0.0

        if not (hra_pct or med_pct or conv_pct):
            return (wage, 0.0, 0.0, 0.0)

        hra = wage * hra_pct
        med = wage * med_pct
        conv = wage * conv_pct
        if currency:
            hra = currency.round(hra)
            med = currency.round(med)
            conv = currency.round(conv)
        return (wage - hra - med - conv, hra, med, conv)

    @api.depends(
        'wage',
        'basic_amount',
        'structure_type_id.working_days_per_month',
        'structure_type_id.absence_base',
    )
    def _compute_daily_wage(self):
        for rec in self:
            st = rec.structure_type_id
            wd = st.working_days_per_month if st else 0.0
            if not wd:
                rec.daily_wage = 0.0
                continue
            base = rec.basic_amount if (st and st.absence_base == 'basic') else (rec.wage or 0.0)
            rec.daily_wage = base / wd
