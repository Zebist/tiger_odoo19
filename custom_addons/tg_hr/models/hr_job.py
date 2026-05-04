# -*- coding: utf-8 -*-

from odoo import fields, models


class HrJob(models.Model):
    _inherit = "hr.job"

    is_manager = fields.Boolean(string="Is Manager", default=False)

    # 权限
    expected_degree = fields.Many2one(groups="hr_recruitment.group_hr_recruitment_interviewer,tg_hr.group_tg_hr_recruitment_applicant_actions")
