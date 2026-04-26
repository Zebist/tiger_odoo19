# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    _STAGE_SEQUENCE = [
        "hr_recruitment.stage_job0",
        "tg_hr.hr_recruitment_stage_tg_initital",
        "tg_hr.hr_recruitment_stage_tg_contacted",
        "tg_hr.hr_recruitment_stage_tg_interview",
        "tg_hr.hr_recruitment_stage_tg_offered",
    ]

    # 进入该阶段前必须满足的字段条件，后续阶段会累积检查前面所有阶段的条件
    _STAGE_ENTRY_REQUIREMENTS = {
        "tg_hr.hr_recruitment_stage_tg_contacted": [
            ("resume_reviewed", "Resume Review"),
        ],
        "tg_hr.hr_recruitment_stage_tg_interview": [
            ("first_contact_made", "First Contact"),
        ],
        "tg_hr.hr_recruitment_stage_tg_offered": [
            ("interview_datetime", "Interview"),
        ],
    }

    stage_id = fields.Many2one(default=lambda r: r.env.ref('hr_recruitment.stage_job0', raise_if_not_found=False))
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

    def archive_applicant(self):
        res = super().archive_applicant()
        refused_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_refused", raise_if_not_found=False
        )
        if refused_stage:
            res.setdefault("context", {})["refused_stage_id"] = refused_stage.id
        return res

    @api.constrains("stage_id")
    def _check_stage_prerequisites(self):
        stage_cache = {}

        def get_stage(xml_id):
            if xml_id not in stage_cache:
                stage_cache[xml_id] = self.env.ref(xml_id, raise_if_not_found=False)
            return stage_cache[xml_id]

        for applicant in self:
            target_index = next(
                (i for i, xid in enumerate(self._STAGE_SEQUENCE)
                 if (s := get_stage(xid)) and s.id == applicant.stage_id.id),
                None,
            )
            if target_index is None:
                continue

            missing = [
                label
                for xid in self._STAGE_SEQUENCE[:target_index + 1]
                for field_name, label in self._STAGE_ENTRY_REQUIREMENTS.get(xid, [])
                if not applicant[field_name]
            ]
            if missing:
                raise ValidationError(
                    _("Cannot move to this stage. Please complete: %s")
                    % ", ".join(missing)
                )

    @api.constrains("review_date")
    def _check_review_date_not_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.review_date and rec.review_date > today:
                raise ValidationError(_("Review Date cannot be in the future."))

    @api.constrains("first_contact_date")
    def _check_first_contact_date_not_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.first_contact_date and rec.first_contact_date > today:
                raise ValidationError(_("First Contact Date cannot be in the future."))

