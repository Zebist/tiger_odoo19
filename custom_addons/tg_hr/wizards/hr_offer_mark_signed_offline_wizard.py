# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrOfferMarkSignedOfflineWizard(models.TransientModel):
    _name = "hr.offer.mark.signed.offline.wizard"
    _description = "Mark Offer Employee Signed Offline"

    offer_id = fields.Many2one(
        "hr.contract.salary.offer",
        string="Offer",
        required=True,
        readonly=True,
    )
    signed_file = fields.Binary(string="Signed Contract (PDF)", required=True)
    signed_filename = fields.Char(string="Filename")
    note = fields.Text(string="Note", help="Optional note recorded in chatter.")

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_groups("tg_hr.group_hr_offer_email_sender,base.group_system"):
            raise UserError(_("You are not allowed to mark offer as signed offline."))

        offer = self.offer_id
        applicant = offer.applicant_id
        if not applicant:
            raise UserError(_("Offer has no linked applicant."))

        # 1. 主附件挂到 applicant（create_employee 时会自动复制到 employee）
        Attachment = self.env["ir.attachment"]
        applicant_attachment = Attachment.create({
            "name": self.signed_filename or _("Signed Contract.pdf"),
            "datas": self.signed_file,
            "res_model": "hr.applicant",
            "res_id": applicant.id,
            "mimetype": "application/pdf",
        })

        # 2. 如果 employee 已创建，副本同步挂到 employee（让 documents_hr 模块能立即收录）
        if applicant.employee_id:
            applicant_attachment.copy({
                "res_model": "hr.employee",
                "res_id": applicant.employee_id.id,
            })

        # 3. cancel 现有 sign_request（电子签流程作废）
        active_requests = offer.sign_request_ids.filtered(
            lambda r: r.state not in ("canceled", "refused", "signed")
        )
        for req in active_requests:
            try:
                req.cancel()
            except Exception:
                _logger.exception("Failed to cancel sign request %s for offer %s", req.id, offer.id)

        # 4. chatter 留痕（offer 上 + applicant 上）
        body = Markup(_(
            "Marked as signed offline. Scanned contract attached: <strong>%s</strong>"
        )) % applicant_attachment.name
        if self.note:
            body += Markup("<br/>%s ") % _("Note:") + (self.note or "")
        offer.message_post(
            body=body,
            attachment_ids=[applicant_attachment.id],
        )

        # 5. 标记签署类型 + 备注，再推进 offer.state → 触发 write hook 推 stage
        offer.sudo().write({
            "sign_type": "offline",
            "offline_sign_note": self.note or False,
            "state": "full_signed",
        })

        return {"type": "ir.actions.client", "tag": "soft_reload"}
