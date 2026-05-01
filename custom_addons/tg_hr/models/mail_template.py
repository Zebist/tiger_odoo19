# -*- coding: utf-8 -*-
from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    # 标记该模板适用于哪些公司，用于 offer 自动挑选默认模板
    company_ids = fields.Many2many(
        "res.company",
        "mail_template_res_company_rel",
        "template_id",
        "company_id",
        string="Applicable Companies",
    )
