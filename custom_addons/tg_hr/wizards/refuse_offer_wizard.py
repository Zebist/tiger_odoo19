from odoo import models, fields
from odoo.exceptions import UserError


class RefuseOfferWizard(models.TransientModel):
    _inherit = 'refuse.offer.wizard'

    def action_refuse(self):
        # csv 已经控制权限，这里直接提权
        return super(RefuseOfferWizard, self.sudo()).action_refuse()
