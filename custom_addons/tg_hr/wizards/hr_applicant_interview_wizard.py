# -*- coding: utf-8 -*-
from odoo import fields, models


class TgHrApplicantInterviewWizard(models.TransientModel):
    _name = "tg.hr.applicant.interview.wizard"
    _description = "Applicant Interview Wizard"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    interview_datetime = fields.Datetime(
        string="Interview Date & Time",
        default=fields.Datetime.now,
        required=True,
    )
    interview_type = fields.Selection(
        selection=[
            ("online", "Online"),
            ("offline", "Offline"),
        ],
        string="Interview Type",
        required=True,
        default="online",
    )
    meeting_url = fields.Char(string="Meeting URL")

    def action_confirm(self):
        self.ensure_one()
        interview_stage = self.env.ref('tg_hr.hr_recruitment_stage_tg_interview', raise_if_not_found=False)
        interview_stage_id = interview_stage if interview_stage else self.env['hr.recruitment.stage']
        self.applicant_id.write(
            {
                "interview_datetime": self.interview_datetime,
                "interview_type": self.interview_type,
                "meeting_url": self.meeting_url,
                "stage_id": interview_stage_id.id
            }
        )
        return {"type": "ir.actions.act_window_close"}

