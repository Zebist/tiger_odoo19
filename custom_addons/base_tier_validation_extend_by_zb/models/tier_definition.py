import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TierDefinition(models.Model):
    _inherit = "tier.definition"

    flow_id = fields.Many2one('base.approval.flow.zb', ondelete='cascade')
    company_id = fields.Many2one(default=lambda r: r.flow_id.company_id.id)
    model_id = fields.Many2one(default=lambda r: r.flow_id.model_id.id)
    stage_res_model = fields.Char(
        string="Stage Model",
        compute="_compute_stage_res_model",
        store=True,
        readonly=True,
    )
    stage_id = fields.Many2oneReference(
        string="Post Approve Stage",
        model_field="stage_res_model",
    )
    rejected_stage_id = fields.Many2oneReference(
        string="Post Reject Stage",
        model_field="stage_res_model",
    )

    @api.depends("model_id")
    def _compute_stage_res_model(self):
        for rec in self:
            rec.stage_res_model = rec.flow_id.stage_model_id.model

    @api.onchange('flow_id')
    def onchange_flow_id(self):
        self.model_id = self.flow_id.model_id
        self.company_id = self.flow_id.company_id
        self.active = self.flow_id.active
