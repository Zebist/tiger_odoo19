# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _name = 'hr.payslip.run'
    _inherit = ['hr.payslip.run', 'tier.validation.zb']

    _tier_validation_manual_config = False
    
    def action_draft(self, *args, **kwargs):
        """Withdraw to Draft —— 两层语义合并：
        1) tier 框架的 withdraw：重置 approval_state、清 reviews
        2) 原生 hr.payslip.run 的：把已 validated 的子 payslip 退回 draft
        显式合并避免 MRO 只走其中一边的歧义。"""
        for run in self:
            run._action_draft(*args, **kwargs)
            run.restart_validation()
            run.review_ids.unlink()
        slip_ids = self.slip_ids.filtered(lambda s: s.state == 'validated')
        if slip_ids:
            slip_ids.action_payslip_draft()
        return True

    def action_paid(self):
        for run in self:
            if run.approval_state != 'approved':
                raise UserError(_(
                    "Pay run '%s' must be approved before marking as paid.",
                    run.name,
                ))
        return super().action_paid()

    def action_payment_report(self, export_format='csv'):
        for run in self:
            if run.approval_state != 'approved':
                raise UserError(_(
                    "Pay run '%s' must be approved before generating payment report.",
                    run.name,
                ))
        return super().action_payment_report(export_format=export_format)
