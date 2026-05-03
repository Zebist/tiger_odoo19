# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # ---- 补充权限
    has_work_entries = fields.Boolean(groups="base.group_system,hr.group_hr_user,tg_hr.group_tg_hr_applicant_records_admin")

    grade = fields.Selection(
        [
            ("G0", "G0"),
            ("G1", "G1"),
            ("G2", "G2"),
            ("G3", "G3"),
            ("G4", "G4"),
            ("G5", "G5"),
            ("G6", "G6"),
            ("G7", "G7"),
            ("G8", "G8"),
            ("G9", "G9"),
        ],
        string="Grade",
        tracking=True,
    )

    # ── HR 入职日期（与合同开始日期不同；HR 招聘流程的入职时间）──────────────
    join_date = fields.Date(
        string="Join Date",
        tracking=True,
        help="HR onboarding date. Distinct from contract start date.",
    )
    trial_date_end = fields.Date(tracking=True)

    # ── 暴露 version_id.contract_date_start 给视图层 invisible 表达式使用 ─
    # 用 related store=False，纯展示用，避免在 hr.version 上加重逻辑
    version_contract_date_start = fields.Date(
        compute="_compute_version_contract_date_start",
        string="Current Contract Start",
        compute_sudo=True,
        readonly=True,
    )

    def _compute_version_contract_date_start(self):
        for rec in self:
            rec.version_contract_date_start = rec.version_id.contract_date_start

    # ── Onboarding Checklist（首次合同 confirm 时填）──────────────────────
    onb_chk_contract_signed = fields.Boolean(string="合同签署", copy=False, tracking=True)
    onb_note_contract_signed = fields.Char(string="合同签署 备注", copy=False)
    onb_chk_equipment_issued = fields.Boolean(string="设备发放", copy=False, tracking=True)
    onb_note_equipment_issued = fields.Char(string="设备发放 备注", copy=False)
    onb_chk_lark_account = fields.Boolean(string="Lark 开通", copy=False, tracking=True)
    onb_note_lark_account = fields.Char(string="Lark 开通 备注", copy=False)
    onb_chk_odoo_account = fields.Boolean(string="Odoo 账号", copy=False, tracking=True)
    onb_note_odoo_account = fields.Char(string="Odoo 账号 备注", copy=False)
    onb_chk_training_completed = fields.Boolean(string="培训完成", copy=False, tracking=True)
    onb_note_training_completed = fields.Char(string="培训完成 备注", copy=False)
    onb_chk_buddy_assigned = fields.Boolean(string="Buddy 对接", copy=False, tracking=True)
    onb_note_buddy_assigned = fields.Char(string="Buddy 对接 备注", copy=False)

    # ── Onboarding 自动检测 helpers（供 confirm wizard 调用）──────────────
    def _onboarding_auto_check_contract_signed(self):
        """合同签署：与 applicant 上「按 id 最新且已审批未拒绝」的 offer 是否 full_signed 一致。"""
        self.ensure_one()
        applicant = self._get_recruitment_applicant()
        if not applicant:
            return False
        offer = applicant._get_latest_approved_offer()
        return bool(offer) and offer.state == "full_signed"

    def _onboarding_auto_check_odoo_account(self):
        """Odoo 账号：employee 是否已关联 user。"""
        self.ensure_one()
        return bool(self.user_id)

    def _onboarding_auto_check_training_completed(self):
        """培训完成：基于 applicant 上的 ob_safety_training_confirmed。"""
        self.ensure_one()
        applicant = self._get_recruitment_applicant()
        return bool(applicant and applicant.ob_safety_training_confirmed)

    def _get_recruitment_applicant(self):
        """获取关联的 applicant：优先用 applicant.employee_id 反查，fallback 到 work_contact_id 匹配。"""
        self.ensure_one()
        Applicant = self.env["hr.applicant"]
        applicant = Applicant.search([("employee_id", "=", self.id)], limit=1, order="id desc")
        if applicant:
            return applicant
        if self.work_contact_id:
            return Applicant.search(
                [("partner_id", "=", self.work_contact_id.id)], limit=1, order="id desc"
            )
        return Applicant

    def action_open_confirm_contract_wizard(self):
        """打开 Confirm Contract wizard（首次入职填合同日期 + onboarding checklist）。"""
        self.ensure_one()
        if not self.env.user.has_groups(
            "tg_hr.group_hr_employee_contract_confirm,base.group_system"
        ):
            raise UserError(_("You are not allowed to confirm employee contracts."))
        return {
            "name": _("Confirm Contract"),
            "type": "ir.actions.act_window",
            "res_model": "hr.employee.confirm.contract.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_employee_id": self.id},
        }

    def push_signed_files_from_offer(self):
        """从 applicant 的最新 signed offer 上拉 signed PDF + Certificate of Completion 到 employee。
        失败仅 log + 不阻塞调用方。
        """
        self.ensure_one()
        applicant = self._get_recruitment_applicant()
        if not applicant:
            _logger.info("push_signed_files: no applicant found for employee %s", self.id)
            return
        try:
            offer = applicant._get_latest_approved_offer()
            if not offer or offer.state != "full_signed":
                _logger.info(
                    "push_signed_files: no latest approved fully-signed offer for applicant %s",
                    applicant.id,
                )
                return
            sign_request = offer.sign_request_ids.filtered(
                lambda r: r.state == "signed"
            ).sorted("id", reverse=True)[:1]
            if not sign_request:
                _logger.info("push_signed_files: no signed sign_request on offer %s", offer.id)
                return
            # signed PDF 通过 sign.request.completed_document_attachment_ids (M2m) 关联，
            # Certificate of Completion 也通过同样途径或 res_model='sign.request' 的附件。
            attachments = sign_request.sudo().completed_document_attachment_ids
            # 也包括直接挂在 sign.request 上的（部分模块这样存）
            attachments |= self.env["ir.attachment"].sudo().search([
                ("res_model", "=", "sign.request"),
                ("res_id", "=", sign_request.id),
                ("mimetype", "=", "application/pdf"),
            ])
            if not attachments:
                _logger.info("push_signed_files: no PDF attachments on sign_request %s", sign_request.id)
                return
            for att in attachments:
                att.copy({
                    "res_model": "hr.employee",
                    "res_id": self.id,
                })
            _logger.info("push_signed_files: pushed %d PDF(s) to employee %s", len(attachments), self.id)
        except Exception:
            _logger.exception(
                "Failed to push signed files from offer to employee %s", self.id
            )
