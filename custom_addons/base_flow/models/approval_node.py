# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ApprovalNode(models.Model):
    _name = 'approval.node'
    _description = 'Approval Node'
    _order = 'flow_id, level, id'

    def _selection_stage_ref(self):
        # 获取 stage 模型
        models_ = self.flow_id.stage_model_id
        return [(m.model, m.name) for m in models_]

    active = fields.Boolean(default=True, required=True)
    flow_id = fields.Many2one(
        'approval.flow',
        string='Flow',
        required=True,
        ondelete='cascade',
        index=True,
    )
    level = fields.Integer(required=True, default=1, index=True)
    name = fields.Char(required=True, translate=True)
    user_id = fields.Many2one(
        'res.users',
        string='Approver',
        ondelete='restrict',
    )
    action_id = fields.Many2one(
        'approval.action',
        string='Action',
        ondelete='set null',
    )
    note = fields.Text()

    company_id = fields.Many2one(
        related='flow_id.company_id',
        store=True,
        readonly=True,
    )
    stage_res_model = fields.Char('Model', readonly=True, related='flow_id.stage_model_id.model')
    stage_id = fields.Many2oneReference('Stage', model_field='stage_res_model')

    @api.constrains('level')
    def _check_level(self):
        """级别不能小于 0, 0是初始节点"""
        for rec in self:
            if rec.level < 0:
                raise ValidationError(_('Level must be greater than or equal to 0.'))

