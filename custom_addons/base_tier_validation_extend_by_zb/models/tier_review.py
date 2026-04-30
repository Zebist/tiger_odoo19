# -*- coding: utf-8 -*-
import pytz

from odoo import api, models


class TierReview(models.Model):
    _inherit = "tier.review"

    @api.depends_context("tz")
    def _compute_reviewed_formated_date(self):
        # 覆盖 OCA 原版以消除 self._context 的 19.0 deprecation warning。
        # 行为一致：UTC reviewed_date → 转用户时区显示。
        timezone = self.env.context.get("tz") or self.env.user.partner_id.tz or "UTC"
        for review in self:
            if not review.reviewed_date:
                review.reviewed_formated_date = False
                continue
            reviewed_date_utc = pytz.timezone("UTC").localize(review.reviewed_date)
            reviewed_date_tz = reviewed_date_utc.astimezone(pytz.timezone(timezone))
            review.reviewed_formated_date = reviewed_date_tz.replace(tzinfo=None)
