# -*- coding: utf-8 -*-
from odoo import fields, models


class TgHrApplicantFirstContactWizard(models.TransientModel):
    _name = "tg.hr.applicant.first.contact.wizard"
    _description = "Applicant First Contact Wizard"

    applicant_id = fields.Many2one("hr.applicant", required=True, ondelete="cascade")
    first_contact_date = fields.Date(string="First Contact Date", default=fields.Date.context_today, required=True)

    def action_confirm(self):
        self.ensure_one()
        contacted_stage = self.env.ref("tg_hr.hr_recruitment_stage_tg_contact", raise_if_not_found=False)
        self.applicant_id.write(
            {
                "first_contact_made": True,
                "first_contact_date": self.first_contact_date,
                "stage_id": contacted_stage.id if contacted_stage else {},
            }
        )
        return {"type": "ir.actions.act_window_close"}

