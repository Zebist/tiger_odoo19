# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SignRequest(models.Model):
    _inherit = "sign.request"

    def _sign(self):
        # 默认 hr_contract_salary 只在候选人走 /salary_package/... controller 完成签署
        # 时才把 offer.state 设为 'full_signed'。我们的流程是 HR 创建 sign_request
        # 后直接发 /sign/document/<id>/<token> 链接给候选人 → 不经过那个 controller，
        # offer.state 永远不会变 → 我们的 stage 推进 write hook 不触发。
        # 这里 hook _sign() 兜底：sign 完成时主动把 offer.state 写成 full_signed，
        # 触发 hr.contract.salary.offer.write → _on_offer_fully_signed 推 stage。
        result = super()._sign()
        for sign_request in self:
            ref = sign_request.reference_doc
            if not ref or ref._name != "hr.contract.salary.offer":
                continue
            if not ref.exists():
                continue
            if ref.state == "full_signed":
                continue
            try:
                ref.sudo().write({"state": "full_signed"})
            except Exception:
                _logger.exception(
                    "Failed to mark offer %s as full_signed after sign completion (sign_request %s)",
                    ref.id, sign_request.id,
                )
        return result
