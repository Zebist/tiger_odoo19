# -*- coding: utf-8 -*-
from odoo import models


class ApplicantGetRefuseReason(models.TransientModel):
    _inherit = "applicant.get.refuse.reason"

    def action_refuse_reason_apply(self):
        applicants = self.applicant_ids
        res = super().action_refuse_reason_apply()
        refused_stage_id = self.env.context.get("refused_stage_id")
        if refused_stage_id:
            # super() sets active=False; re-activate and move to Refused stage
            # so the record stays visible in the Refused kanban column
            applicants.with_context(active_test=False).write({
                "active": True,
                "stage_id": refused_stage_id,
            })
        return res
