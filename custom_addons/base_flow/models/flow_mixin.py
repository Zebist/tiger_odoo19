# -*- coding: utf-8 -*-

from odoo import Command, fields, models, _
from odoo.exceptions import UserError


class FlowMixin(models.AbstractModel):
    _name = 'flow.mixin'
    _description = 'Flow Mixin'

    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approving', 'Approving'),
            ('exception', 'Exception'),
            ('rejected', 'Rejected'),
            ('approved', 'Approved'),
        ],
        string='Status',
        required=True,
        default='draft',
        index=True,
        copy=False,
        tracking=True,
        readonly=True
    )
    #
    # approve_note = fields.Text(
    #     string='Approval Note',
    #     copy=False,
    #     tracking=True,
    #     readonly=True
    # )
    #
    # company_id = fields.Many2one(
    #     'res.company', string='Company', required=True, default=lambda self: self.env.company,
    # )
    # approval_runtime_id = fields.Many2one(
    #     'approval.runtime',
    #     string='Approval Runtime',
    #     copy=False,
    #     index=True,
    #     readonly=True,
    # )
    # is_current_approver = fields.Boolean(compute_sudo=True, compute='_compute_is_current_approver', store=False)
    # is_create_user = fields.Boolean(compute_sudo=True, compute='_compute_is_create_user', store=False)
    # flow_id = fields.Many2one('approval.flow')
    #
    # def _compute_is_create_user(self):
    #     for rec in self:
    #         rec.is_create_user = rec.create_uid == self.env.user
    #
    # def _compute_is_current_approver(self):
    #     for rec in self:
    #         runtime = rec.approval_runtime_id
    #         if runtime and runtime.current_line_id and runtime.current_line_id.state == 'pending':
    #             rec.is_current_approver = runtime.current_line_id.node_id.user_id == self.env.user
    #         else:
    #             rec.is_current_approver = False
    #
    # def _require_state(self, allowed_states, action_label=None):
    #     self.ensure_one()
    #     if self.state not in allowed_states:
    #         label = action_label or _('This action')
    #         raise UserError(_('%(label)s is only allowed in status: %(states)s.') % {
    #             'label': label,
    #             'states': ', '.join(allowed_states),
    #         })
    #
    # def update_stage(self, next_node_id):
    #     # 更新 stage
    #     self.ensure_one()
    #     stage_field = self._fields.get('stage_id')
    #     current_stage = getattr(self, 'stage_id', None)
    #     current_stage_id = getattr(current_stage, 'id', False)
    #     if stage_field and next_node_id.stage_id and current_stage_id and current_stage_id != next_node_id.stage_id:
    #         self.write({stage_field.name: next_node_id.stage_id})
    #
    # def action_submit(self):
    #     """提交操作
    #     1. 重新获取单据审批流-运行态
    #     2. 更新下 stage
    #     """
    #     if not self.is_creator():
    #         raise UserError(_('Only the creator can operate.'))
    #     self = self.sudo()  # 确认是创建人后提权
    #
    #     for rec in self:
    #         rec._require_state({'draft'}, action_label=_('Submit'))
    #
    #     Flow = self.env['approval.flow'].sudo()
    #     # 每次提交重新获取单据审批流
    #     for rec in self:
    #         if rec.approval_runtime_id:
    #             rec.approval_runtime_id.unlink()
    #             rec.approval_runtime_id = False
    #
    #         flow = Flow.search([
    #             ('active', '=', True),
    #             ('company_id', '=', rec.company_id.id),
    #             ('model_id.model', '=', rec._name),
    #         ], limit=1)
    #         if not flow:
    #             raise UserError(_('No approval flow found for this document.'))
    #         rec.flow_id = flow
    #
    #         nodes = flow.get_nodes()
    #         if not nodes:
    #             raise UserError(_('Approval flow has no active nodes.'))
    #
    #         # 创建单据审批流运行态
    #         runtime = self.env['approval.runtime'].sudo().create({
    #             'flow_id': flow.id,
    #             'document_ref': f'{rec._name},{rec.id}',
    #             'line_ids': [Command.create({'node_id': node.id}) for node in nodes],
    #         })
    #         runtime.current_line_id = runtime.line_ids.filtered(lambda r: r.level != 0).sorted(lambda l: l.level)[:1].id
    #         rec.update_stage(runtime.current_line_id.node_id)
    #
    #         rec.write({
    #             'approval_runtime_id': runtime.id,
    #             'state': 'approving',
    #             'approve_note': '',
    #         })
    #
    # def _check_approve_perm(self, node_id):
    #     """检查审批权限并提权"""
    #     if self.env.user != node_id.user_id:
    #         raise UserError(_('You are not allowed to approve this document.'))
    #
    #     return self.sudo()
    #
    # def action_approve(self):
    #     """
    #     审批通过
    #     1. 进入下一级
    #     2. 如果没有下级，完成审批流
    #     3. 执行审批动作 action
    #     """
    #     self = self._check_approve_perm(self.approval_runtime_id.current_line_id.node_id)
    #
    #     for rec in self:
    #         rec._require_state({'approving'}, action_label=_('Approve'))
    #
    #     now = fields.Datetime.now()
    #     for rec in self:
    #         runtime = rec.approval_runtime_id
    #         if not runtime:
    #             rec.state = 'approved'
    #             continue
    #
    #         current = runtime.current_line_id
    #         if current and current.state == 'pending':
    #             current.write({
    #                 'state': 'approved',
    #                 'action_by': self.env.user.id,
    #                 'action_date': now,
    #             })
    #             action = current.node_id.action_id
    #             if action and action.active:
    #                 action.run(document=rec, runtime_line=current)
    #
    #         next_line = runtime.line_ids.filtered(lambda l: l.state == 'pending' and l.level != 0).sorted(lambda l: l.level)[:1]
    #         runtime.current_line_id = next_line.id or False
    #
    #         self.update_stage(next_line.node_id)
    #         rec.state = 'approved' if not next_line else 'approving'
    #
    # def action_reject(self):
    #     """
    #     审批拒绝
    #     1. 更新stage 和 state
    #     """
    #     self = self._check_approve_perm(self.approval_runtime_id.current_line_id.node_id)
    #
    #     for rec in self:
    #         rec._require_state({'approving'}, action_label=_('Reject'))
    #
    #     now = fields.Datetime.now()
    #     for rec in self:
    #         runtime = rec.approval_runtime_id
    #         if runtime and runtime.current_line_id and runtime.current_line_id.state == 'pending':
    #             runtime.current_line_id.write({
    #                 'state': 'rejected',
    #                 'action_by': self.env.user.id,
    #                 'action_date': now,
    #             })
    #             runtime.current_line_id = False
    #         init_node = rec.flow_id.get_node(0)  # 获取初始节点，用于更新 stage
    #         rec.state = 'rejected'
    #         rec.update_stage(init_node[0])
    #
    # def action_open_reject_wizard(self):
    #     """打开拒绝原因向导（确认后会调用 action_reject）。"""
    #     self.ensure_one()
    #     self._require_state({'approving'}, action_label=_('Reject'))
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _('Reject'),
    #         'res_model': 'approval.reject.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'active_model': self._name,
    #             'active_id': self.id,
    #             'active_ids': self.ids,
    #             'default_note': self.approve_note,
    #         },
    #     }
    #
    # def action_set_exception(self):
    #     for rec in self:
    #         rec._require_state({'approving'}, action_label=_('Set Exception'))
    #     self.write({'state': 'exception'})
    #
    # def is_creator(self):
    #     """是否提单人"""
    #     self.ensure_one()
    #     return self.env.user == self.create_uid
    #
    # def action_reset_to_draft(self):
    #     """
    #     重置state 和 stage
    #     """
    #     if not self.is_creator():
    #         raise UserError(_('Only the creator can operate.'))
    #     self = self.sudo()  # 确认是创建人后提权
    #
    #     for rec in self:
    #         rec._require_state({'rejected', 'exception'}, action_label=_('Reset to Draft'))
    #
    #     for rec in self:
    #         if rec.approval_runtime_id:
    #             rec.approval_runtime_id.unlink()
    #             rec.approval_runtime_id = False
    #         init_node = rec.flow_id.get_node(0)
    #         rec.state = 'draft'
    #         rec.update_stage(init_node[0])
    #
