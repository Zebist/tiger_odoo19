# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class ApprovalRejectWizard(models.TransientModel):
    _name = 'approval.reject.wizard'
    _description = 'Approval Reject Wizard'

    note = fields.Text(string='Reject Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if not active_model or not active_id:
            raise UserError(_('Missing active document in context.'))

        doc = self.env[active_model].browse(active_id)
        if not doc.exists():
            raise UserError(_('The document no longer exists.'))

        if 'approve_note' in doc._fields:
            doc.write({'approve_note': self.note})

        action_reject = getattr(doc, 'action_reject', None)
        if not action_reject:
            raise UserError(_('This document does not support reject action.'))
        action_reject()
        return {'type': 'ir.actions.act_window_close'}

