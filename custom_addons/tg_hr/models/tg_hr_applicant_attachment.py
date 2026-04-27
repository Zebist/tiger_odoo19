# -*- coding: utf-8 -*-
from odoo import api, fields, models

ATTACHMENT_TYPE_SELECTION = [
    ('nid', 'National ID'),
    ('passport', 'Passport'),
    ('work_permit', 'Work Permit'),
    ('diploma', 'Diploma'),
    ('resignation_proof', 'Resignation Proof'),
    ('other', 'Other'),
]

TYPE_LABEL = dict(ATTACHMENT_TYPE_SELECTION)


class TgHrApplicantAttachment(models.Model):
    _name = 'tg.hr.applicant.attachment'
    _description = 'Onboarding Document'
    _order = 'attachment_type, id'

    applicant_id = fields.Many2one('hr.applicant', required=True, ondelete='cascade', index=True)
    attachment_type = fields.Selection(ATTACHMENT_TYPE_SELECTION, string='Type', required=True)
    name = fields.Char(
        string='Document Name',
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    file = fields.Binary(string='File', required=True)
    file_filename = fields.Char()

    @api.depends('attachment_type', 'applicant_id.partner_name')
    def _compute_name(self):
        for rec in self:
            if rec.attachment_type:
                label = TYPE_LABEL.get(rec.attachment_type, rec.attachment_type)
                applicant_name = rec.applicant_id.partner_name or ''
                rec.name = f'{label} - {applicant_name}' if applicant_name else label
            else:
                rec.name = False
