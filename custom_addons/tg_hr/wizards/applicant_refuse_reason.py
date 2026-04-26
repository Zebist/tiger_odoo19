# -*- coding: utf-8 -*-
from odoo import models


class ApplicantGetRefuseReason(models.TransientModel):
    _inherit = "applicant.get.refuse.reason"

    def action_refuse_reason_apply(self):
        refused_stage_id = self.env.context.get("refused_stage_id")
        if refused_stage_id:
            self.applicant_ids.write({"stage_id": refused_stage_id})
        return super().action_refuse_reason_apply()
