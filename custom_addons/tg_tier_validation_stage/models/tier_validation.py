import logging

from odoo import models

_logger = logging.getLogger(__name__)


class TierValidation(models.AbstractModel):
    _inherit = "tier.validation.zb"

    def _server_action_tier(self, reviews, status):
        # Keep original behaviour (server actions) first.
        res = super()._server_action_tier(reviews, status)

        # Prevent recursion when stage write triggers tier validation again.
        if self.env.context.get("tier_stage_write"):
            return res

        for review in reviews:
            definition = review.definition_id
            stage = (
                definition.stage_id
                if status == "approved"
                else definition.rejected_stage_id
                if status == "rejected"
                else False
            )
            if not stage:
                continue

            doc = self.env[review.model].browse(review.res_id)
            if not doc:
                continue

            stage_field = doc._fields.get("stage_id")
            if not stage_field:
                _logger.exception(
                    "Skip tier stage update: %s has no stage_id field",
                    doc._name,
                )
                continue

            if getattr(stage_field, "comodel_name", None) and (
                stage_field.comodel_name != definition.stage_res_model
            ):
                _logger.exception(
                    "Skip tier stage update: %s.stage_id comodel is %s, got %s",
                    doc._name,
                    stage_field.comodel_name,
                    definition.stage_res_model,
                )
                continue

            # Consistent with server action execution: run as superuser.
            doc.sudo().with_context(
                tier_stage_write=True,
                skip_tier_state_check=True,
                skip_validation_check=True,
            ).write({"stage_id": stage})

        return res

