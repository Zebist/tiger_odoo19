import logging
from odoo import models, fields


_logger = logging.getLogger(__name__)


class TierValidation(models.AbstractModel):
    _name = 'tier.validation.zb'
    _inherit = "tier.validation"
    # draft 和 approving 为了实现 submig
    _state_from = ['rejected', 'approving']
    _state_to = ['approved']

    flow_id = fields.Many2one('base.approval.flow.zb')
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('approving', 'Approving'),
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

    def _tier_validation_check_state_on_write(self, vals):
        if self.env.context.get("skip_tier_state_check"):
            return

        return super()._tier_validation_check_state_on_write(vals)

    def request_validation(self):
        """
        @Override
        按 tier.definition.sequence（小的优先）生成 tier.review，并保持同一套 sequence 语义。

        OCA `base_tier_validation` 默认会按 `tier.definition.sequence desc` 取定义，
        然后将命中的定义重编号为 tier.review.sequence = 1..N，这会让“定义 sequence”
        和“审批层级 sequence”语义相反。

        这里统一逻辑：
        - tier.definition.sequence 越小，越先审批
        - tier.review.sequence 直接等于 tier.definition.sequence（不再重编号）
        """
        td_obj = self.env["tier.definition"]
        tr_obj = self.env["tier.review"]
        vals_list = []
        for rec in self:
            if rec._check_state_from_condition() and rec.need_validation:
                tier_definitions = td_obj.search(
                    [
                        ("model", "=", self._name),
                        ("company_id", "in", [False] + rec._get_company().ids),
                    ],
                    order="sequence asc",
                )
                for td in tier_definitions:
                    if rec.evaluate_tier(td):
                        vals_list.append(rec._prepare_tier_review_vals(td, td.sequence))
        created_trs = tr_obj.create(vals_list)
        if any(self.mapped("can_review")):
            self._update_counter({"review_created": True})
        self._notify_review_requested(created_trs)
        return created_trs

    def validate_tier(self):
        """
        @Override 重写，加个dont_need_comment，用来给 submit 跳过
        """
        self.ensure_one()
        sequences = self._get_sequences_to_approve(self.env.user)
        reviews = self.review_ids.filtered(
            lambda x: x.sequence in sequences or x.approve_sequence_bypass
        )
        # 这里重写，加个dont_need_comment，用来给 submit 跳过
        if self.has_comment and not self.env.context.get('dont_need_comment'):
            user_reviews = reviews.filtered(
                lambda r: r.status == "pending" and (self.env.user in r.reviewer_ids)
            )
            return self._add_comment("validate", user_reviews)
        self._validate_tier(reviews)
        self._update_counter({"review_deleted": True})

    def _server_action_tier(self, reviews, status):
        """审批节点回调：在 server action / stage 更新之后，同步维护业务 state。

        说明：
        - `base_tier_validation` 只维护 tier.review/validation_status，不会自动写业务 state。
        - 我们在此统一将：
          - 任意 reject -> state=rejected
          - 全部通过（validation_status=validated） -> state=approved
        """
        # Keep original behaviour (server actions) first.
        res = super()._server_action_tier(reviews, status)

        # Prevent recursion when stage write triggers tier validation again.
        # if self.env.context.get("tier_stage_write"):
        #     return res

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
                # tier_stage_write=True,
                skip_tier_state_check=True,
                skip_validation_check=True,
            ).write({"stage_id": stage})

        for rec in self:
            target_state = False
            if status == "rejected":
                target_state = "rejected"
            elif status == "approved" and rec.validation_status == "validated":
                target_state = "approved"

            if target_state and rec.state != target_state:
                rec.sudo().with_context(
                    # tier_state_write=True,
                    skip_tier_state_check=True,
                    skip_validation_check=True,
                ).write({"state": target_state})

        return res

    def _action_draft(self):
        """重置草稿"""
        for rec in self:
            if 'stage_id' not in rec._fields:
                continue
            if not rec.review_ids:
                continue

            self.sudo().with_context(
                # tier_stage_write=True,
                skip_tier_state_check=True,
                skip_validation_check=True,
            ).write({"stage_id": rec.review_ids[0].definition_id.flow_id.draft_stage_id})
        self.sudo().with_context(
            # tier_stage_write=True,
            skip_tier_state_check=True,
            skip_validation_check=True,
        ).write({"state": 'draft'})

    def action_submit(self):
        """从 Draft 提交到 Submitted（不触发 Tier 审批拦截）。"""
        for rec in self:
            rec.sudo().with_context(
                # tier_state_write=True,
                skip_tier_state_check=True,
                skip_validation_check=True,
            ).write({"state": "approving"})
            reviews = rec.request_validation()  # 自动请求validation  # todo 做成可配置
            if not reviews:
                continue
            submit_stage_id = reviews[0].definition_id.flow_id.submit_stage_id
            if 'stage_id' in rec._fields:
                rec.sudo().with_context(
                    skip_tier_state_check=True,
                    skip_validation_check=True,
                ).write({"stage_id": submit_stage_id})

        return True

    def action_ack(self):
        """确认拒绝原因，回到草稿状态"""
        self._action_draft()
        self.restart_validation()

    def action_draft(self):
        """撤回到草稿状态"""
        self._action_draft()
        self.restart_validation()
