# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ApprovalRuntime(models.Model):
    _name = 'approval.runtime'
    _description = 'Approval Runtime'
    _order = 'id desc'

    def _selection_document_ref(self):
        # Not user-configured; filled automatically from business documents.
        # Keep it generic for now to support all non-transient models.
        models_ = self.env['ir.model'].sudo().search([('transient', '=', False)])
        return [(m.model, m.name) for m in models_]

    flow_id = fields.Many2one(
        'approval.flow',
        string='Flow',
        required=True,
        ondelete='restrict',
        index=True,
    )
    document_ref = fields.Reference(
        selection=_selection_document_ref,
        string='Document',
        required=True,
        index=True,
    )

    line_ids = fields.One2many(
        'approval.runtime.line',
        'runtime_id',
        string='Lines',
        copy=False,
    )
    current_line_id = fields.Many2one(
        'approval.runtime.line',
        string='Current Line',
        copy=False,
        ondelete='set null',
    )

    _sql_constraints = [
        ('document_ref_uniq', 'unique(document_ref)', _('Only one runtime is allowed per document.')),
    ]

