# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BaseApprovalFlow(models.Model):
    _name = 'base.approval.flow.zb'
    _description = 'Approval Flow'
    _order = 'name, id'

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True, required=True)
    allow_delete = fields.Boolean(string='Allow delete', default=False)
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
    stage_model_field = fields.Char(related='stage_model_id.model')

    definition_ids = fields.One2many(
        'tier.definition',
        'flow_id',
        string='Definitions',
        copy=True,
    )
    submit_stage_id = fields.Many2oneReference(
        string="Submit Stage",
        model_field="stage_model_field",
    )
    draft_stage_id = fields.Many2oneReference(
        string="Draft Stage",
        model_field="stage_model_field",
    )
    reject_stage_id = fields.Many2oneReference(
        string="Reject Stage",
        model_field="stage_model_field",
    )
    approve_stage_id = fields.Many2oneReference(
        string="Approved Stage",
        model_field="stage_model_field",
    )

    @api.onchange('model_id')
    def onchange_model_id(self):
        """自动设置 stage_model_id"""

        model_name = self.model_id.model
        if not model_name:
            self.stage_model_id = False

        stage_model = f"{model_name}.stage"
        self.stage_model_id = self.env['ir.model'].search([('model', '=', stage_model)], limit=1)

    def write(self, vals):
        if 'active' in vals:  # 向子级同步 active
            self.definition_ids.write({'active': vals['active']})

        return super().write(vals)
