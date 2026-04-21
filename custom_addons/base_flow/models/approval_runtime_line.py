# -*- coding: utf-8 -*-

from odoo import fields, models, _


class ApprovalRuntimeLine(models.Model):
    _name = 'approval.runtime.line'
    _description = 'Approval Runtime Line'
    _order = 'runtime_id, level, id'

    runtime_id = fields.Many2one(
        'approval.runtime',
        string='Runtime',
        required=True,
        ondelete='cascade',
        index=True,
    )
    node_id = fields.Many2one(
        'approval.node',
        string='Node',
        required=True,
        ondelete='restrict',
        index=True,
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        required=True,
        default='pending',
        index=True,
    )

    level = fields.Integer(related='node_id.level', store=True, index=True, readonly=True)
    approver_id = fields.Many2one(related='node_id.user_id', store=True, index=True, readonly=True)

    action_by = fields.Many2one('res.users', string='Action By', copy=False, index=True)
    action_date = fields.Datetime(string='Action Date', copy=False, index=True)
    note = fields.Text(string='Note', copy=False)

    _sql_constraints = [
        ('runtime_node_uniq', 'unique(runtime_id, node_id)', _('A node can only appear once per runtime.')),
    ]

