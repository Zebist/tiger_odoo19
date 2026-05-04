from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    # 权限

    role_line_ids = fields.One2many(
        groups="base.group_erp_manager,tg_hr.group_tg_hr_onboarding_records_core",
    )