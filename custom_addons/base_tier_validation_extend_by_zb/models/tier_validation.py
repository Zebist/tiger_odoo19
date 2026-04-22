from odoo import models, fields


class TierValidation(models.AbstractModel):
    _inherit = "tier.validation"
    # draft 和 approving 为了实现 submig
    _state_from = ['draft', 'approving']
    _state_to = ['approving', 'approved']

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

    def _tier_validation_check_state_on_write(self, vals):
        if self.env.context.get("skip_tier_state_check"):
            return
        return super()._tier_validation_check_state_on_write(vals)

    def action_submit(self):
        """从 Draft 提交到 Submitted（不触发 Tier 审批拦截）。"""
        for rec in self:
            reviews = rec.request_validation()  # 自动请求validation  # todo 做成可配置
            # 自动执行一次“当前用户可审批的层级”，以触发 server action（例如更新 stage）
            if reviews:
                reviews._compute_can_review()
                rec.with_context(dont_need_comment=True).validate_tier()  # 自动submit
        return True

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
