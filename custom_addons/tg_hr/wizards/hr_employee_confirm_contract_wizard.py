# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# 6 项 checklist 的代码定义（与 employee 上 onb_chk_* / onb_note_* 字段对应）
CHECKLIST_ITEMS = [
    ('contract_signed', '合同签署', '_onboarding_auto_check_contract_signed'),
    ('equipment_issued', '设备发放', None),
    ('lark_account', 'Lark 开通', None),
    ('odoo_account', 'Odoo 账号', '_onboarding_auto_check_odoo_account'),
    ('training_completed', '培训完成', '_onboarding_auto_check_training_completed'),
    ('buddy_assigned', 'Buddy 对接', None),
]


class HrEmployeeConfirmContractWizard(models.TransientModel):
    _name = 'hr.employee.confirm.contract.wizard'
    _description = 'Confirm Employee Contract'

    employee_id = fields.Many2one('hr.employee', required=True, readonly=True)

    # ── Contract Dates ────────────────────────────────────────────────────
    contract_date_start = fields.Date(
        string='Contract Start',
        required=True,
        default=lambda self: self._default_contract_date_start(),
    )
    trial_period_months = fields.Integer(
        string='Trial Period (Months)',
        default=lambda self: self._default_trial_period_months(),
    )
    trial_date_end = fields.Date(
        string='End of Trial Period',
        compute='_compute_trial_date_end',
        store=True,
        readonly=True,
    )
    contract_date_end = fields.Date(
        string='Contract End',
        required=True,
        compute='_compute_contract_date_end',
        store=True,
        readonly=False,
    )
    trial_in_progress = fields.Boolean(
        string='Trial Still in Progress',
        compute='_compute_trial_in_progress',
        help="True when trial_date_end is today or later — contract end is locked to trial end.",
    )

    # ── Onboarding Checklist (6 items) ────────────────────────────────────
    chk_contract_signed = fields.Boolean(string='合同签署')
    note_contract_signed = fields.Char(string='合同签署 备注')
    is_auto_contract_signed = fields.Boolean(readonly=True)

    chk_equipment_issued = fields.Boolean(string='设备发放')
    note_equipment_issued = fields.Char(string='设备发放 备注')
    is_auto_equipment_issued = fields.Boolean(readonly=True)

    chk_lark_account = fields.Boolean(string='Lark 开通')
    note_lark_account = fields.Char(string='Lark 开通 备注')
    is_auto_lark_account = fields.Boolean(readonly=True)

    chk_odoo_account = fields.Boolean(string='Odoo 账号')
    note_odoo_account = fields.Char(string='Odoo 账号 备注')
    is_auto_odoo_account = fields.Boolean(readonly=True)

    chk_training_completed = fields.Boolean(string='培训完成')
    note_training_completed = fields.Char(string='培训完成 备注')
    is_auto_training_completed = fields.Boolean(readonly=True)

    chk_buddy_assigned = fields.Boolean(string='Buddy 对接')
    note_buddy_assigned = fields.Char(string='Buddy 对接 备注')
    is_auto_buddy_assigned = fields.Boolean(readonly=True)

    # ── Defaults ──────────────────────────────────────────────────────────
    @api.model
    def _default_contract_date_start(self):
        emp_id = self.env.context.get('default_employee_id')
        if emp_id:
            emp = self.env['hr.employee'].browse(emp_id)
            return emp.join_date or fields.Date.context_today(self)
        return fields.Date.context_today(self)

    @api.model
    def _default_trial_period_months(self):
        emp_id = self.env.context.get('default_employee_id')
        if emp_id:
            emp = self.env['hr.employee'].browse(emp_id)
            applicant = emp._get_recruitment_applicant()
            if applicant and applicant.ob_trial_period_months:
                return applicant.ob_trial_period_months
        return 6

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        emp_id = vals.get('employee_id') or self.env.context.get('default_employee_id')
        if emp_id:
            emp = self.env['hr.employee'].browse(emp_id)
            for code, _label, auto_method in CHECKLIST_ITEMS:
                detected = False
                if auto_method and hasattr(emp, auto_method):
                    try:
                        detected = bool(getattr(emp, auto_method)())
                    except Exception:
                        _logger.exception(
                            "Onboarding auto-detect %s failed on employee %s",
                            auto_method, emp.id,
                        )
                vals[f'is_auto_{code}'] = detected
                # 自动检测为 True 时默认勾选；HR 仍然可以手动取消
                vals[f'chk_{code}'] = detected or bool(emp[f'onb_chk_{code}'])
                # 已有 note 默认带过来
                vals[f'note_{code}'] = emp[f'onb_note_{code}'] or False
        return vals

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('contract_date_start', 'trial_period_months')
    def _compute_trial_date_end(self):
        for wiz in self:
            if wiz.contract_date_start and wiz.trial_period_months:
                wiz.trial_date_end = wiz.contract_date_start + relativedelta(months=wiz.trial_period_months)
            else:
                wiz.trial_date_end = False

    @api.depends('trial_date_end')
    def _compute_trial_in_progress(self):
        today = fields.Date.context_today(self)
        for wiz in self:
            wiz.trial_in_progress = bool(wiz.trial_date_end and wiz.trial_date_end > today)

    @api.depends('trial_date_end', 'trial_in_progress')
    def _compute_contract_date_end(self):
        # 试用期未结束：强制 contract_date_end = trial_date_end（前端 readonly 配合 force_save=1 写入）
        for wiz in self:
            if wiz.trial_in_progress and wiz.trial_date_end:
                wiz.contract_date_end = wiz.trial_date_end
            elif not wiz.contract_date_end:
                wiz.contract_date_end = wiz.trial_date_end or False

    # ── note 填了自动勾 chk（HR 觉得"已经做完事"就直接写备注，不用先点 checkbox）──
    @api.onchange("note_contract_signed")
    def _onchange_note_contract_signed(self):
        if self.note_contract_signed and self.note_contract_signed.strip():
            self.chk_contract_signed = True

    @api.onchange("note_equipment_issued")
    def _onchange_note_equipment_issued(self):
        if self.note_equipment_issued and self.note_equipment_issued.strip():
            self.chk_equipment_issued = True

    @api.onchange("note_lark_account")
    def _onchange_note_lark_account(self):
        if self.note_lark_account and self.note_lark_account.strip():
            self.chk_lark_account = True

    @api.onchange("note_odoo_account")
    def _onchange_note_odoo_account(self):
        if self.note_odoo_account and self.note_odoo_account.strip():
            self.chk_odoo_account = True

    @api.onchange("note_training_completed")
    def _onchange_note_training_completed(self):
        if self.note_training_completed and self.note_training_completed.strip():
            self.chk_training_completed = True

    @api.onchange("note_buddy_assigned")
    def _onchange_note_buddy_assigned(self):
        if self.note_buddy_assigned and self.note_buddy_assigned.strip():
            self.chk_buddy_assigned = True

    # ── Confirm ───────────────────────────────────────────────────────────
    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_groups(
            "tg_hr.group_hr_employee_contract_confirm,base.group_system"
        ):
            raise UserError(_("You are not allowed to confirm employee contracts."))

        # 校验 6 项 checklist
        missing_done = []
        missing_notes = []
        for code, label, _auto in CHECKLIST_ITEMS:
            done = self[f'chk_{code}']
            note = self[f'note_{code}']
            is_auto = self[f'is_auto_{code}']
            if not done:
                missing_done.append(label)
            elif done and not is_auto and not (note and note.strip()):
                # 手动勾选必须填备注（自动检测的不需要）
                missing_notes.append(label)
        if missing_done:
            raise UserError(_(
                "All checklist items must be checked. Missing: %s",
                ", ".join(missing_done),
            ))
        if missing_notes:
            raise UserError(_(
                "Please add a note for these manually-checked items: %s",
                ", ".join(missing_notes),
            ))

        if not self.contract_date_start:
            raise UserError(_("Contract start date is required."))
        if not self.contract_date_end:
            raise UserError(_("Contract end date is required."))
        if self.contract_date_end < self.contract_date_start:
            raise UserError(_("Contract end date cannot be earlier than the start date."))

        # 写入 employee + version
        emp_vals = {}
        for code, _label, _auto in CHECKLIST_ITEMS:
            emp_vals[f'onb_chk_{code}'] = self[f'chk_{code}']
            emp_vals[f'onb_note_{code}'] = self[f'note_{code}'] or False
        self.employee_id.write(emp_vals)

        version = self.employee_id.sudo().version_id
        version.write({
            'contract_date_start': self.contract_date_start,
            'contract_date_end': self.contract_date_end,
            'trial_date_end': self.trial_date_end,
        })

        # chatter 记录摘要
        try:
            lines = []
            for code, label, _auto in CHECKLIST_ITEMS:
                done = self[f'chk_{code}']
                is_auto = self[f'is_auto_{code}']
                note = self[f'note_{code}'] or ''
                mark = '✓' if done else '✗'
                source = ' (auto)' if is_auto else (f' — {note}' if note else '')
                lines.append(f'<li>{mark} <strong>{label}</strong>{source}</li>')
            body = Markup(
                '<p>%s</p>'
                '<p>Contract: %s → %s; Trial end: %s</p>'
                '<ul>%s</ul>'
            ) % (
                _("Contract confirmed."),
                self.contract_date_start,
                self.contract_date_end,
                self.trial_date_end or '-',
                Markup('').join(Markup(line) for line in lines),
            )
            self.employee_id.message_post(body=body)
        except Exception:
            _logger.exception("Failed to post confirm-contract chatter for employee %s", self.employee_id.id)

        return {"type": "ir.actions.client", "tag": "soft_reload"}
