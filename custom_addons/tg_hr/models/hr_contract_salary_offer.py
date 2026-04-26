# -*- coding: utf-8 -*-
from odoo import models


class HrContractSalaryOffer(models.Model):
    _name = "hr.contract.salary.offer"
    _inherit = ["hr.contract.salary.offer", "tier.validation.zb"]

    _tier_validation_manual_config = False
