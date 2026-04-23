# -*- coding: utf-8 -*-
from odoo import fields, models


class TgHrApplicantReviewWizard(models.TransientModel):
    _name = "tg.hr.applicant.review.wizard"
    _description = "Applicant Resume Review Wizard"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    priority = fields.Selection(
        selection=[
            ("0", "Not Rated"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        string="Initial Screening Score",
        default="0",
        required=True,
    )
    review_date = fields.Date(string="Review Date", default=fields.Date.context_today, required=True)

    def action_confirm(self):
        self.ensure_one()
        vals = {
            "priority": self.priority,
            "resume_reviewed": True,
            "review_date": self.review_date,
        }
        self.applicant_id.write(vals)
        return {"type": "ir.actions.act_window_close"}

