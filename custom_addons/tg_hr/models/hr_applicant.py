# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    show_review_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_first_contact_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_interview_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 是否处于 Interview 阶段（控制面试分组显隐）
    is_in_interview_stage = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 非 New 阶段时为 True（控制 Interview Process 页显隐）
    show_interview_process_page = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )

    requisition_id = fields.Many2one(
        "tg.hr.requisition",
        string="Requisition",
        tracking=True,
        ondelete="set null",
    )

    priority = fields.Selection(
        selection=[
            ("0", "Not Rated"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        default="0",
        tracking=True,
        string="Initial Screening Score"
    )

    resume_reviewed = fields.Boolean(string="Resume Reviewed", default=False, tracking=True, compute='_compute_resume_reviewd', readonly=True, compute_sudo=True)
    review_date = fields.Date(string="Review Date", tracking=True)
    initial_screening_notes = fields.Html(string="Initial Screening Notes", tracking=True)

    first_contact_made = fields.Boolean(string="First Contact Made", default=False, tracking=True, compute='_compute_first_contact_made', readonly=True, compute_sudo=True)
    first_contact_date = fields.Date(string="First Contact Date", tracking=True)

    interview_score = fields.Selection(
        selection=[
            ("0", "Not Rated"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        string="Interview Score",
        default="0",
        tracking=True,
    )
    interview_datetime = fields.Datetime(string="Interview Date & Time", tracking=True)
    interview_type = fields.Selection(
        selection=[
            ("online", "Online"),
            ("offline", "Offline"),
        ],
        string="Interview Type",
        tracking=True,
    )
    meeting_url = fields.Char(string="Meeting URL", tracking=True)
    interview_notes = fields.Html(string="Interview Notes", tracking=True)

    assigned_hr_id = fields.Many2one(
        "res.users",
        string="Assigned HR",
        default=lambda self: self.env.user,
        tracking=True,
        domain=[("share", "=", False)],
    )

    @api.depends('review_date')
    def _compute_resume_reviewd(self):
        for rec in self:
            rec.resume_reviewed = bool(rec.review_date)

    @api.depends('first_contact_date')
    def _compute_first_contact_made(self):
        for rec in self:
            rec.first_contact_made = bool(rec.first_contact_date)

    @api.depends("stage_id", "resume_reviewed", "first_contact_made")
    def _compute_tg_hr_stage_flags(self):
        init_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_initital", raise_if_not_found=False
        )
        init_stage_id = init_stage if init_stage else False
        contacted_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_contacted", raise_if_not_found=False
        )
        contacted_stage_id = contacted_stage if contacted_stage else False
        interview_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_interview", raise_if_not_found=False
        )
        interview_stage_id = interview_stage if interview_stage else False
        # Odoo 内置的 New 阶段，用于判断是否隐藏 Interview Process 页
        new_stage = self.env.ref(
            "hr_recruitment.stage_job0", raise_if_not_found=False
        )
        new_stage_id = new_stage if new_stage else False
        for applicant in self:
            stage_id = applicant.stage_id
            applicant.show_review_button = bool(stage_id == init_stage_id and not applicant.resume_reviewed)
            applicant.show_first_contact_button = bool(stage_id == init_stage_id and applicant.resume_reviewed)
            applicant.show_interview_button = bool(stage_id == contacted_stage_id and applicant.first_contact_made)
            applicant.is_in_interview_stage = bool(stage_id == interview_stage_id)
            # 有阶段且不是 New 阶段时显示 Interview Process 页
            applicant.show_interview_process_page = bool(stage_id and stage_id != new_stage_id)

    def action_open_review_wizard(self):
        self.ensure_one()
        return {
            "name": self.env._("Resume Review"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
                "default_review_date": fields.Date.context_today(self),
                "default_resume_reviewed": True,
                "default_priority": self.priority,
            },
        }

    def action_open_first_contact_wizard(self):
        self.ensure_one()
        return {
            "name": self.env._("First Contact"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.first.contact.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
                "default_first_contact_date": fields.Date.context_today(self),
                "default_first_contact_made": True,
            },
        }

    def action_open_interview_wizard(self):
        self.ensure_one()
        return {
            "name": self.env._("Interview Details"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.interview.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
            },
        }

    @api.constrains("stage_id", "resume_reviewed")
    def _check_resume_review_before_contacted(self):
        contacted_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_contacted", raise_if_not_found=False
        )
        if not contacted_stage:
            return
        for applicant in self:
            if applicant.stage_id.id == contacted_stage.id and not applicant.resume_reviewed:
                raise ValidationError(
                    _("You must complete Resume Review before moving to Contacted.")
                )

    @api.constrains("stage_id", "first_contact_made")
    def _check_first_contact_before_interview(self):
        interview_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_interview", raise_if_not_found=False
        )
        if not interview_stage:
            return
        for applicant in self:
            if applicant.stage_id.id == interview_stage.id and not applicant.first_contact_made:
                raise ValidationError(
                    _("You must complete First Contact before moving to Interview.")
                )

