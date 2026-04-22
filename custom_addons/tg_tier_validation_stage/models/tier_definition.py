import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class TierDefinition(models.Model):
    _inherit = "tier.definition"

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
            model_name = rec.model_id.model
            if not model_name:
                rec.stage_res_model = False
                continue
            stage_model = f"{model_name}.stage"
            if stage_model not in rec.env:
                # Keep it empty so Many2oneReference has no target model.
                # This avoids crashing when the stage model isn't installed.
                _logger.exception(
                    "Stage model %s not found in registry for tier.definition %s",
                    stage_model,
                    rec.id or "(new)",
                )
                rec.stage_res_model = False
                continue
            rec.stage_res_model = stage_model

    @api.constrains("stage_id", "rejected_stage_id", "stage_res_model")
    def _check_stage_model_available(self):
        for rec in self:
            if (rec.stage_id or rec.rejected_stage_id) and not rec.stage_res_model:
                raise ValidationError(
                    _(
                        "Stage model is not available for this referenced model. "
                        "Please ensure the stage model is installed."
                    )
                )

