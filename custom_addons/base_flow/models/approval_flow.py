# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ApprovalFlow(models.Model):
    _name = 'approval.flow'
    _description = 'Approval Flow'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True, required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
    )
    stage_model_id = fields.Many2one(
        'ir.model',
        string='Stage Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False), ('name', 'ilike', '%stage%')],
    )
    description = fields.Text()

    node_ids = fields.One2many(
        'approval.node',
        'flow_id',
        string='Nodes',
        copy=True,
    )

    @api.constrains('node_ids')
    def _check_node_ids(self):
        for flow in self:
            levels = [n.level for n in flow.node_ids if n.active]
            if len(levels) != len(set(levels)):
                raise ValidationError(_('Node level must be unique per flow.'))
            init_nodes = flow.node_ids.filtered(lambda r: r.level == 0)
            if len(init_nodes) > 1:
                raise ValidationError(_('There can only be one initial node.'))
            if not init_nodes:
                raise ValidationError(_('There must be an initial node.'))

    def get_node(self, level):
        """
        获取指定级别节点
        level 0 初始节点 n 指定节点 负数是结束节点
        """
        self.ensure_one()
        return self.node_ids.filtered(lambda n: n.active and n.level == level).sorted(lambda n: n.level)

    def get_nodes(self):
        """获取所有启用节点"""
        self.ensure_one()
        return self.node_ids.filtered(lambda n: n.active).sorted(lambda n: n.level)

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class TigerApprovalFlow(models.Model):
    _name = 'approval.flow'
    _description = 'Approval Flow'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True, required=True)
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
    )
    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False)],
    )
    stage_model_id = fields.Many2one(
        'ir.model',
        string='Stage Model',
        required=True,
        ondelete='cascade',
        domain=[('transient', '=', False), ('name', 'ilike', '%stage%')],
    )
    description = fields.Text()

    node_ids = fields.One2many(
        'approval.node',
        'flow_id',
        string='Nodes',
        copy=True,
    )

    @api.constrains('node_ids')
    def _check_node_ids(self):
        for flow in self:
            levels = [n.level for n in flow.node_ids if n.active]
            if len(levels) != len(set(levels)):
                raise ValidationError(_('Node level must be unique per flow.'))
            init_nodes = flow.node_ids.filtered(lambda r: r.level == 0)
            if len(init_nodes) > 1:
                raise ValidationError(_('There can only be one initial node.'))
            if not init_nodes:
                raise ValidationError(_('There must be an initial node.'))

    def get_node(self, level):
        """
        获取指定级别节点
        level 0 初始节点 n 指定节点 负数是结束节点
        """
        self.ensure_one()
        return self.node_ids.filtered(lambda n: n.active and n.level == level).sorted(lambda n: n.level)

    def get_nodes(self):
        """获取所有启用节点"""
        self.ensure_one()
        return self.node_ids.filtered(lambda n: n.active).sorted(lambda n: n.level)

