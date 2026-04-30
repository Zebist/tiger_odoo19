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
    # 视图绑定用：合同没配 KPI Base 时整块 KPI Grade 区域不显示
    kpi_base = fields.Monetary(related='version_id.kpi_base', readonly=True)
    # KPIBONUS 输入与 KPI Grade 预期值不一致时的提示文案，空字符串表示一致或无需检查
    kpi_input_mismatch_message = fields.Char(
        compute='_compute_kpi_input_mismatch_message',
    )

    @api.depends('kpi_grade', 'version_id.kpi_base')
    def _compute_kpi_grade_amount(self):
        for slip in self:
            if not slip.kpi_grade:
                slip.kpi_grade_amount = 0.0
                continue
            rate = KPI_GRADE_RATES.get(slip.kpi_grade, 0.0)
            slip.kpi_grade_amount = (slip.version_id.kpi_base or 0.0) * rate

    @api.depends('kpi_grade', 'kpi_grade_amount', 'input_line_ids.amount', 'input_line_ids.code')
    def _compute_kpi_input_mismatch_message(self):
        for slip in self:
            if not slip.kpi_grade:
                slip.kpi_input_mismatch_message = False
                continue
            kpi_inputs = slip.input_line_ids.filtered(lambda l: l.code == KPI_INPUT_CODE)
            if not kpi_inputs:
                slip.kpi_input_mismatch_message = False
                continue
            actual = sum(kpi_inputs.mapped('amount'))
            currency = slip.currency_id or slip.company_id.currency_id
            if currency and currency.compare_amounts(actual, slip.kpi_grade_amount) != 0:
                slip.kpi_input_mismatch_message = _(
                    "KPIBONUS input is %(actual)s, but KPI Grade %(grade)s expects %(expected)s. "
                    "Click Apply to sync, or adjust the input manually.",
                    actual=currency.format(actual),
                    grade=slip.kpi_grade,
                    expected=currency.format(slip.kpi_grade_amount),
                )
            else:
                slip.kpi_input_mismatch_message = False

    def action_apply_kpi_grade(self):
        """显式按钮：根据 KPI Grade 添加/更新 KPIBONUS input 行，落 chatter + 弹通知。"""
        self.ensure_one()
        if self.state in ('cancel', 'validated', 'paid'):
            raise UserError(_("Cannot modify KPIBONUS when the payslip is %s.", self.state))
        if not self.kpi_grade:
            raise UserError(_("Please select a KPI Grade first."))

        kpi_type = self.env['hr.payslip.input.type'].search([('code', '=', KPI_INPUT_CODE)], limit=1)
        if not kpi_type:
            raise UserError(_(
                "KPIBONUS payslip input type not found. "
                "Please ensure the input type with code '%s' exists.", KPI_INPUT_CODE))

        existing = self.input_line_ids.filtered(lambda l: l.code == KPI_INPUT_CODE)
        old_amount = existing[0].amount if existing else None
        new_amount = self.kpi_grade_amount

        # 写入 / 创建（带 sync ctx 绕过 _check_kpi_grade_conflict）
        if existing:
            existing[0].with_context(**{_KPI_SYNC_CTX: True}).write({'amount': new_amount})
            if len(existing) > 1:
                existing[1:].with_context(**{_KPI_SYNC_CTX: True}).unlink()
        else:
            self.env['hr.payslip.input'].with_context(**{_KPI_SYNC_CTX: True}).create({
                'payslip_id': self.id,
                'input_type_id': kpi_type.id,
                'amount': new_amount,
                'name': kpi_type.name,
            })

        # 无 version 的草稿 payslip 上 currency_id 为 False，回退到公司币
        currency = self.currency_id or self.company_id.currency_id
        kpi_base = self.version_id.kpi_base or 0.0
        if old_amount is None:
            title = _("KPIBONUS added")
            body = _("Added KPIBONUS input: %(amt)s (Grade %(grade)s × Base %(base)s)",
                     amt=currency.format(new_amount or 0.0),
                     grade=self.kpi_grade,
                     base=currency.format(kpi_base))
        elif old_amount != new_amount:
            title = _("KPIBONUS updated")
            body = _("Updated KPIBONUS input: %(old)s → %(new)s (Grade %(grade)s × Base %(base)s)",
                     old=currency.format(old_amount),
                     new=currency.format(new_amount or 0.0),
                     grade=self.kpi_grade,
                     base=currency.format(kpi_base))
        else:
            title = _("KPIBONUS unchanged")
            body = _("KPIBONUS already equals %(amt)s — nothing to update.",
                     amt=currency.format(new_amount or 0.0))

        self.message_post(body=body, subtype_xmlid='mail.mt_note')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': body,
                'type': 'success',
                'sticky': False,
                'next': {

                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                }
            },
        }



    # ------------------------------------------------------------------
    # 薪资规则辅助方法
    # 设计原则：每条有逻辑的薪资规则在这里对应一个方法，规则 XML 只调一行。
    # 后续新结构需要相同逻辑时直接复用方法，不重复写 Python 代码。x
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

class HrPayslipInput(models.Model):
    _inherit = 'hr.payslip.input'

    def _check_kpi_input_conflict(self):
        """KPIBONUS 唯一性守门：同一 payslip 上 KPIBONUS 行唯一，
        防重复导入 / 重复手填导致双倍发钱。
        Apply 按钮通过 _KPI_SYNC_CTX 绕过此检查（按钮内部走 update 而非 create）。"""
        if self.env.context.get(_KPI_SYNC_CTX):
            return
        for inp in self:
            if inp.code != KPI_INPUT_CODE:
                continue
            siblings = inp.payslip_id.input_line_ids.filtered(
                lambda l: l.code == KPI_INPUT_CODE and l.id != inp.id
            )
            if siblings:
                raise UserError(_(
                    "Payslip '%(slip)s' already has a KPIBONUS input "
                    "(amount %(amt)s). KPIBONUS must be unique per payslip — "
                    "update the existing line instead of adding a new one.",
                    slip=inp.payslip_id.display_name,
                    amt=siblings[0].amount,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_kpi_input_conflict()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {'amount', 'input_type_id', 'payslip_id'} & set(vals):
            self._check_kpi_input_conflict()
        return res
