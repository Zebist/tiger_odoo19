# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

KPI_INPUT_CODE = 'KPIBONUS'
KPI_GRADE_RATES = {'A': 1.0, 'B': 0.5, 'C': 0.0}
_KPI_SYNC_CTX = 'tg_payroll_kpi_sync'


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    kpi_grade = fields.Selection(
        [('A', 'A (100%)'), ('B', 'B (50%)'), ('C', 'C (0%)')],
        string="KPI Grade",
        help="If set, the KPIBONUS input is auto-computed from the contract's KPI Base "
             "and this grade. Manual entry or import of KPIBONUS is blocked while a grade "
             "is selected — clear the grade first to allow manual values.",
    )
    kpi_grade_amount = fields.Monetary(
        string="KPI Grade Amount",
        compute='_compute_kpi_grade_amount',
        help="Auto-computed KPI bonus based on KPI Grade and the contract's KPI Base.",
    )

    @api.depends('kpi_grade', 'version_id.kpi_base')
    def _compute_kpi_grade_amount(self):
        for slip in self:
            if not slip.kpi_grade:
                slip.kpi_grade_amount = 0.0
                continue
            rate = KPI_GRADE_RATES.get(slip.kpi_grade, 0.0)
            slip.kpi_grade_amount = (slip.version_id.kpi_base or 0.0) * rate

    @api.onchange('kpi_grade')
    def _onchange_kpi_grade(self):
        # 客户端预览：即时反映在 input 行
        kpi_type = self.env['hr.payslip.input.type'].search(
            [('code', '=', KPI_INPUT_CODE)], limit=1)
        for slip in self:
            existing = slip.input_line_ids.filtered(lambda l: l.code == KPI_INPUT_CODE)
            if slip.kpi_grade:
                amount = slip.kpi_grade_amount
                if existing:
                    existing[0].amount = amount
                    if len(existing) > 1:
                        slip.input_line_ids -= existing[1:]
                elif kpi_type:
                    slip.input_line_ids = [(0, 0, {
                        'input_type_id': kpi_type.id,
                        'amount': amount,
                        'name': kpi_type.name,
                    })]
            elif existing:
                slip.input_line_ids -= existing

    def _sync_kpi_grade_input(self):
        # 服务端落库同步（保险一手，覆盖直接 write 的场景）
        kpi_type = self.env['hr.payslip.input.type'].search(
            [('code', '=', KPI_INPUT_CODE)], limit=1)
        for slip in self:
            existing = slip.input_line_ids.filtered(lambda l: l.code == KPI_INPUT_CODE)
            if slip.kpi_grade:
                amount = slip.kpi_grade_amount
                ctx_self = self.env['hr.payslip.input'].with_context(**{_KPI_SYNC_CTX: True})
                if existing:
                    existing[0].with_context(**{_KPI_SYNC_CTX: True}).write({'amount': amount})
                    if len(existing) > 1:
                        existing[1:].with_context(**{_KPI_SYNC_CTX: True}).unlink()
                elif kpi_type:
                    ctx_self.create({
                        'payslip_id': slip.id,
                        'input_type_id': kpi_type.id,
                        'amount': amount,
                        'name': kpi_type.name,
                    })
            elif existing:
                existing.with_context(**{_KPI_SYNC_CTX: True}).unlink()

    # ------------------------------------------------------------------
    # 薪资规则辅助方法
    # 设计原则：每条有逻辑的薪资规则在这里对应一个方法，规则 XML 只调一行。
    # 后续新结构需要相同逻辑时直接复用方法，不重复写 Python 代码。
    # ------------------------------------------------------------------

    def _prorate(self, amount):
        """按合同在 payslip 期间的有效天数折算金额（处理跨月入/离职）。
        规则用法：result = payslip._prorate(version.basic_amount)
        """
        self.ensure_one()
        version = self.version_id
        from_dt = self.date_from
        to_dt = self.date_to
        total_days = (to_dt - from_dt).days + 1
        contract_start = version.date_start or from_dt
        contract_end = version.date_end or to_dt
        actual_start = max(contract_start, from_dt)
        actual_end = min(contract_end, to_dt)
        active_days = max((actual_end - actual_start).days + 1, 0)
        return (amount or 0.0) / total_days * active_days

    def _input_amount(self, code):
        """取 payslip 上指定 code 的 input 金额，不存在时返回 0。"""
        self.ensure_one()
        inp = self.input_line_ids.filtered(lambda l: l.code == code)
        return inp[0].amount if inp else 0.0

    def _compute_ot(self):
        """加班费：OT_hours × version.overtime（合同上的每小时加班费）。"""
        self.ensure_one()
        return self._input_amount('OT') * (self.version_id.overtime or 0.0)

    def _compute_perfect_attend(self):
        """全勤奖：当月无缺勤（ABS == 0）则返回 version.perfect_attend_amount。"""
        self.ensure_one()
        return self.version_id.perfect_attend_amount if self._input_amount('ABS') == 0 else 0.0

    def _compute_adj(self):
        """调整金额：直读 ADJ input（夜班/产量奖以外的临时调整）。"""
        self.ensure_one()
        return self._input_amount('ADJ')

    def _compute_expat_pay(self):
        """外派津贴：EXPAT_days × version.expat_daily。"""
        self.ensure_one()
        return self._input_amount('EXPAT') * (self.version_id.expat_daily or 0.0)

    def _compute_trip_pay(self):
        """出差补助：TRIP_days × version.trip_daily。"""
        self.ensure_one()
        return self._input_amount('TRIP') * (self.version_id.trip_daily or 0.0)

    def _compute_cn_ct_attendance_pay(self):
        """中国外包（日薪×出勤）：
        result = (monthly_wage / 26) × max(26 - ABS_days, 0)

        ABS_days 取 ABS input（天）。
        """
        self.ensure_one()
        st = self.version_id.structure_type_id
        standard_days = st.working_days_per_month or 26.0

        abs_days = self._input_amount('ABS') or 0.0
        attendance_days = max(standard_days - abs_days, 0.0)
        monthly_wage = self.version_id.wage or 0.0
        return (monthly_wage / standard_days) * attendance_days

    def _compute_late_ded(self):
        """迟到扣款：读 struct type 的 late_rate_mode 分支。
        wage_based: per_min = wage / (working_days × hours_per_day × 60)
        fixed:      per_min = late_fixed_per_minute（struct type 配置）
        """
        self.ensure_one()
        st = self.version_id.structure_type_id
        late_hours = self._input_amount('LATE')
        if st.late_rate_mode == 'fixed':
            per_min = st.late_fixed_per_minute or 0.0
        else:
            working_days = st.working_days_per_month or 26.0
            cal = self.version_id.resource_calendar_id
            hours_per_day = cal.hours_per_day if cal else 8.0
            per_min = (self.version_id.wage or 0.0) / (working_days * hours_per_day * 60.0)
        return -(late_hours * 60.0) * per_min

    def _compute_abs_ded(self):
        """缺勤扣款：ABS_days × (wage / working_days_per_month)。"""
        self.ensure_one()
        working_days = self.version_id.structure_type_id.working_days_per_month or 26.0
        per_day = (self.version_id.wage or 0.0) / working_days
        return -self._input_amount('ABS') * per_day

    def _compute_ait(self):
        """孟加拉 AIT 月度个税（阶梯税表 + 性别 + 3% rebate + 年税 min 5000 + 跨月折算）。
        被各 BD 结构的 AIT 薪资规则调用：result = payslip._compute_ait()
        后续新增 BD 结构的 AIT 规则直接复用这一行即可。
        """
        self.ensure_one()
        version = self.version_id
        total_days = (self.date_to - self.date_from).days + 1
        contract_start = version.date_start or self.date_from
        contract_end = version.date_end or self.date_to
        active_start = max(contract_start, self.date_from)
        active_end = min(contract_end, self.date_to)
        active_days = max((active_end - active_start).days + 1, 0)

        monthly_wage = version.wage or 0.0
        annual_income = monthly_wage * 13.0
        tax_free = min(annual_income / 3.0, 450000.0)
        taxable = annual_income - tax_free

        sex = self.employee_id.sex
        if sex == 'male':
            slabs = [
                (350000, 0.00),
                (100000, 0.05),
                (400000, 0.10),
                (500000, 0.15),
                (500000, 0.20),
                (2000000, 0.25),
            ]
        else:
            slabs = [
                (400000, 0.00),
                (100000, 0.05),
                (400000, 0.10),
                (500000, 0.15),
                (500000, 0.20),
                (2000000, 0.25),
            ]

        remaining = taxable
        tax = 0.0
        for limit, rate in slabs:
            if remaining <= 0:
                break
            slab_amount = min(remaining, limit)
            tax += slab_amount * rate
            remaining -= slab_amount
        if remaining > 0:
            tax += remaining * 0.25

        if not tax:
            return 0.0
        rebate = taxable * 0.03
        annual_tax = max(tax - rebate, 5000.0)
        monthly_tax = annual_tax / 12.0
        if active_days < total_days:
            monthly_tax = monthly_tax / total_days * active_days
        return -monthly_tax

    def write(self, vals):
        res = super().write(vals)
        if 'kpi_grade' in vals or 'version_id' in vals:
            self._sync_kpi_grade_input()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        slips = super().create(vals_list)
        slips_with_grade = slips.filtered('kpi_grade')
        if slips_with_grade:
            slips_with_grade._sync_kpi_grade_input()
        return slips


class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    def _check_kpi_grade_conflict(self):
        if self.env.context.get(_KPI_SYNC_CTX):
            return
        for inp in self:
            if inp.code == KPI_INPUT_CODE and inp.payslip_id.kpi_grade:
                raise UserError(_(
                    "Cannot set KPIBONUS input on payslip '%(slip)s' while KPI Grade "
                    "is selected (%(grade)s). Clear the KPI Grade first to allow manual "
                    "or imported KPIBONUS values.",
                    slip=inp.payslip_id.display_name,
                    grade=inp.payslip_id.kpi_grade,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_kpi_grade_conflict()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'amount', 'input_type_id', 'payslip_id'} & set(vals):
            self._check_kpi_grade_conflict()
        return res
