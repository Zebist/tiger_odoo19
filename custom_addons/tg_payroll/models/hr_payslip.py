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
