# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrApplicantCreateEmployeeWizard(models.TransientModel):
    _name = 'tg.hr.applicant.create.employee.wizard'
    _description = 'Create Employee Wizard'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    manager_id = fields.Many2one('hr.employee', string='Reporting Manager', required=True,
                                 options="{'no_quick_create': True}")
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Work Location',
        required=True,
        default=lambda self: self._default_work_location_id(),
        domain="[('company_id', 'in', [False, applicant_company_id])]",
    )
    applicant_company_id = fields.Many2one(related='applicant_id.company_id')
    resource_calendar_id = fields.Many2one('resource.calendar', string='Working Schedule',
                                           required=True, check_company=True)

    # ── Join Date / Contract End Date ─────────────────────────────────────
    join_date = fields.Date(
        string='Join Date',
        required=True,
        default=lambda self: self._default_join_date(),
        help="The date the employee starts onboarding. Distinct from contract start date.",
    )
    trial_date_end = fields.Date(
        string='Trial End Date',
        required=True,
        compute='_compute_trial_date_end',
        store=True,
        readonly=False,
        help="Defaults to join_date + trial period. The contract dates (start / end) are confirmed "
             "later via 'Confirm Contract' on the employee form.",
    )

    @api.model
    def _default_join_date(self):
        applicant_id = self.env.context.get('default_applicant_id') or self.env.context.get('active_id')
        if applicant_id:
            applicant = self.env['hr.applicant'].browse(applicant_id)
            offer = applicant._get_latest_approved_offer()
            if offer and offer.contract_start_date:
                return offer.contract_start_date
        return fields.Date.context_today(self)

    @api.model
    def _default_work_location_id(self):
        # 与 join_date 一致：取「按 id 最新、已审批、未拒绝」的 offer 上的 Location
        applicant_id = self.env.context.get('default_applicant_id') or self.env.context.get('active_id')
        if applicant_id:
            applicant = self.env['hr.applicant'].browse(applicant_id)
            offer = applicant._get_latest_approved_offer()
            if offer and offer.work_location_id:
                return offer.work_location_id.id
        return False

    @api.depends('join_date', 'applicant_id.ob_trial_period_months')
    def _compute_trial_date_end(self):
        for wiz in self:
            months = wiz.applicant_id.ob_trial_period_months or 0
            if wiz.join_date and months:
                wiz.trial_date_end = wiz.join_date + relativedelta(months=months)
            elif wiz.join_date:
                # 没设试用期默认 6 个月
                wiz.trial_date_end = wiz.join_date + relativedelta(months=6)
            else:
                wiz.trial_date_end = False

    def action_create_employee(self):
        if self.env.user.has_group('tg_hr.group_tg_hr_onboarding_create_employee'):
            self = self.sudo()  # 有创建权限时提权

        self.ensure_one()
        applicant = self.applicant_id
        applicant.write({
            'department_id': self.department_id.id,
            'ob_manager_id': self.manager_id.id,
            'work_location_id': self.work_location_id.id,
        })
        # 用 context 把 join_date 传到 _get_employee_create_vals 让 trial_end 从 join_date 算
        action = applicant.with_context(
            tg_hr_create_employee_join_date=self.join_date,
        ).create_employee_from_applicant()
        employee = self.env['hr.employee'].browse(action.get('res_id'))
        if employee:
            employee.resource_calendar_id = self.resource_calendar_id.id
            # 显式覆盖（_get_employee_create_vals 已写入 join_date，但保险起见 + 写 contract_date_end）
            employee.write({'join_date': self.join_date})
            version = employee.sudo().version_id
            version_vals = {
                'work_location_id': self.work_location_id.id,
                'trial_date_end': self.trial_date_end,
                # 注意：不写 contract_date_start / contract_date_end —— hr.version 上有 SQL constraint
                # 要求 contract_date_end 非空时 contract_date_start 必填；我们让 HR 走 Confirm Contract
                # 时一并填齐两个日期。这里只暂存 trial_date_end，作为 Confirm Contract wizard 的默认值。
            }
            # 从 offer 同步 wage（applicant -> offer.wage 已经在审批前算好）
            offer = applicant._get_latest_approved_offer()
            if offer and offer.wage:
                version_vals['wage'] = offer.wage
            # 入职档案角色对 hr.version 可能仅只读，统一 sudo 写入向导落库字段
            version.sudo().write(version_vals)
            # Push 签好的合同 PDF + Certificate of Completion 到 employee
            employee.push_signed_files_from_offer()
        return action
