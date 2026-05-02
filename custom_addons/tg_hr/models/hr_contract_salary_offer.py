# -*- coding: utf-8 -*-
import datetime
import logging
from datetime import timedelta

from odoo import _, api, fields, models, Command
from odoo.addons.base_by_zb.tools.amount import amount_to_chinese_upper
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrContractSalaryOffer(models.Model):
    _name = "hr.contract.salary.offer"
    _inherit = ["hr.contract.salary.offer", "tier.validation.zb"]

    _tier_validation_manual_config = False

    reporting_to_id = fields.Many2one("hr.employee", string="Reporting To", required=True, tracking=True)
    work_location_id = fields.Many2one(
        "hr.work.location",
        string="Location",
        required=True,
        tracking=True,
        compute="_compute_work_location_id_default_from_applicant",
        store=True,
        readonly=False,
        domain="[('company_id', 'in', [False, company_id])]",
    )

    company_signer_id = fields.Many2one(
        "res.users",
        string="Company Signer",
        compute="_compute_company_signer_id",
        store=True,
        readonly=False,
        tracking=True,
        help="The company-side signer for the offer letter. Defaults to the HR Responsible "
             "configured on the contract template; can be overridden per offer.",
    )

    wage = fields.Monetary(
        string="Wage",
        required=True,
        default=0.0,
        currency_field="currency_id",
        compute="_compute_wage_default_from_applicant",
        store=True,
        readonly=False,
        tracking=True,
    )
    structure_type_id = fields.Many2one(
        'hr.payroll.structure.type',
        string="Salary Structure Type",
        related="contract_template_id.structure_type_id",
        store=True,
        readonly=True,
    )

    basic_salary = fields.Monetary(string="Basic Salary", compute="_compute_salary_breakdown", store=True, currency_field="currency_id")
    house_rent_allowance = fields.Monetary(string="House Rent Allowance", compute="_compute_salary_breakdown", store=True, currency_field="currency_id")
    medical_allowance = fields.Monetary(string="Medical Allowance", compute="_compute_salary_breakdown", store=True, currency_field="currency_id")
    conveyance_allowance = fields.Monetary(string="Conveyance Allowance", compute="_compute_salary_breakdown", store=True, currency_field="currency_id")

    offer_total_amount = fields.Monetary(
        string="Total",
        compute="_compute_offer_total_amount",
        store=True,
        currency_field="currency_id",
    )

    basic_salary_upper_zh = fields.Char(
        string="Basic Salary (Upper)",
        compute="_compute_basic_salary_upper_zh",
        store=True,
        readonly=False
    )

    # ── Offer Email ──────────────────────────────────────────────────────
    email_template_id = fields.Many2one(
        "mail.template",
        string="Offer Email Template",
        compute="_compute_email_template_id",
        store=True,
        readonly=False,
        domain="[('model', '=', 'hr.contract.salary.offer'), '|', ('company_ids', '=', False), ('company_ids', 'in', company_id)]",
    )
    working_time_text = fields.Char(
        string="Working Time",
        compute="_compute_working_time_text",
        store=True,
        readonly=False,
        tracking=True,
        help="Working hours text shown in the offer email, e.g. '9:30 to 18:30'.",
    )
    offer_sender_id = fields.Many2one(
        "res.users",
        string="Offer Sender",
        compute="_compute_offer_sender_id",
        store=True,
        readonly=False,
        tracking=True,
        help="Shown as the sender (From) of the offer email when set. Defaults to the applicant's Assigned HR.",
    )
    offer_email_recipient = fields.Char(
        string="Recipient Email",
        related="applicant_id.email_from",
        readonly=True,
    )
    offer_email_sent_date = fields.Datetime(string="Offer Email Sent On", readonly=True, copy=False)
    offer_email_state = fields.Selection(
        [("not_sent", "Not Sent"), ("sent", "Sent"), ("failed", "Failed")],
        string="Offer Email Status",
        default="not_sent",
        readonly=True,
        copy=False,
    )

    # ── Sign Request 状态字段（用于按钮 invisible + 视觉显示） ─────────────
    has_sign_request = fields.Boolean(
        string="Has Active Sign Request",
        compute="_compute_sign_request_state",
        store=True,
    )
    is_company_signed = fields.Boolean(
        string="Company Signed",
        compute="_compute_sign_request_state",
        store=True,
    )
    is_employee_signed = fields.Boolean(
        string="Employee Signed",
        compute="_compute_sign_request_state",
        store=True,
    )
    sign_invite_sent_to_employee = fields.Datetime(
        string="Sign Invitation Sent On",
        readonly=True,
        copy=False,
        help="Timestamp of the last time HR sent the sign link to the candidate.",
    )
    sign_type = fields.Selection(
        [("online", "Online"), ("offline", "Offline")],
        string="Sign Type",
        readonly=True,
        copy=False,
        help="How the offer was signed: online (Odoo Sign flow) or offline (paper signed, scan uploaded).",
    )
    is_offer_for_current_user = fields.Boolean(
        compute="_compute_is_offer_for_current_user",
        compute_sudo=True,
        help="True when the current logged-in user is the applicant of this offer "
             "(used to gate the Employee Sign button to the candidate only).",
    )
    offline_sign_note = fields.Text(
        string="Offline Sign Note",
        readonly=True,
        copy=False,
        help="Optional note recorded by HR when marking offline signed.",
    )

    SIGN_PREFILL_MAPPING = {
        "EMPLOYEE NAME": lambda o: o.applicant_id.partner_name or "",
        "POSITION": lambda o: o.employee_job_id.name or o.job_title or "",
        "DEPARTMENT": lambda o: o.department_id.name or "",
        "POSITION & DEPARTMENT": lambda o: " / ".join(filter(None, [
            o.employee_job_id.name or o.job_title or "",
            o.department_id.name or "",
        ])),
        "REPORTING TO": lambda o: o.reporting_to_id.name or "",
        "LOCATION": lambda o: (o.work_location_id.name or "") if o.work_location_id else "",
        "JOB LOCATION": lambda o: (o.work_location_id.name or "") if o.work_location_id else "",
        "DATE OF JOINING": lambda o: o.contract_start_date or "",
        "DATE START": lambda o: o.contract_start_date or "",
        "DATE END": lambda o: o.contract_end_date or _("Unlimited"),
        "BASIC SALARY": lambda o: o.basic_salary,
        "HOUSE RENT ALLOWANCE": lambda o: o.house_rent_allowance,
        "MEDICAL ALLOWANCE": lambda o: o.medical_allowance,
        "CONVEYANCE ALLOWANCE": lambda o: o.conveyance_allowance,
        "TOTAL": lambda o: o.offer_total_amount,
        "COMPANY NAME": lambda o: o.company_id.name or "",
        "BASIC SALARY（UPPER）": lambda o: o.basic_salary_upper_zh or "",
    }

    @api.onchange("department_id")
    def _onchange_department_id_set_reporting_to(self):
        # 表单里切换部门时，仅在 Reporting To 为空时回填部门 manager
        for offer in self:
            if not offer.reporting_to_id and offer.department_id.manager_id:
                offer.reporting_to_id = offer.department_id.manager_id

    @api.depends(
        "wage",
        "structure_type_id",
        "structure_type_id.hra_pct",
        "structure_type_id.medical_pct",
        "structure_type_id.conveyance_pct",
    )
    def _compute_salary_breakdown(self):
        # 复用 hr.version 上的同款拆分算法，确保 offer 与合同一致
        Version = self.env['hr.version']
        for offer in self:
            basic, hra, med, conv = Version._split_wage(
                offer.wage, offer.structure_type_id, offer.currency_id
            )
            offer.basic_salary = basic
            offer.house_rent_allowance = hra
            offer.medical_allowance = med
            offer.conveyance_allowance = conv

    @api.depends("basic_salary", "house_rent_allowance", "medical_allowance", "conveyance_allowance")
    def _compute_offer_total_amount(self):
        for offer in self:
            offer.offer_total_amount = (
                (offer.basic_salary or 0.0)
                + (offer.house_rent_allowance or 0.0)
                + (offer.medical_allowance or 0.0)
                + (offer.conveyance_allowance or 0.0)
            )

    @api.depends("basic_salary", "currency_id")
    def _compute_basic_salary_upper_zh(self):
        for offer in self:
            offer.basic_salary_upper_zh = amount_to_chinese_upper(offer.basic_salary or 0.0)

    @api.depends("applicant_id", "applicant_id.assigned_hr_id")
    def _compute_offer_sender_id(self):
        # 与 work_location 类似：仅在为空时回填，避免覆盖 HR 手改；新建时默认 Assigned HR。
        for offer in self:
            if not offer.offer_sender_id and offer.applicant_id.assigned_hr_id:
                offer.offer_sender_id = offer.applicant_id.assigned_hr_id

    @api.depends("company_id")
    def _compute_email_template_id(self):
        # 根据公司挑选默认 offer 邮件模板：模板 company_ids 包含当前公司即匹配。
        # readonly=False 允许手动覆盖；公司变化时会重算（覆盖手选）—— 简单策略，
        # 用户切换公司后请重新检查模板是否需要再调整。
        Template = self.env["mail.template"].sudo()
        for offer in self:
            if not offer.company_id:
                offer.email_template_id = False
                continue
            tmpl = Template.search(
                [
                    ("model", "=", "hr.contract.salary.offer"),
                    ("company_ids", "in", offer.company_id.id),
                ],
                order="id asc",
                limit=1,
            )
            offer.email_template_id = tmpl or False

    @api.depends("applicant_id.work_location_id")
    def _compute_work_location_id_default_from_applicant(self):
        # 创建 / 关联 applicant 时，若 work_location_id 为空，自动取 applicant.work_location_id 作默认值。
        # readonly=False 允许 HR 后续调整。
        for offer in self:
            if not offer.work_location_id and offer.applicant_id.work_location_id:
                offer.work_location_id = offer.applicant_id.work_location_id

    @api.depends("applicant_id.salary_proposed")
    def _compute_wage_default_from_applicant(self):
        # 创建 / 关联 applicant 时，若 wage 为 0/空，自动取 applicant.salary_proposed 作默认值。
        # readonly=False 允许 HR 后续手动调整且不会被覆盖（条件是 wage 已非 0）。
        for offer in self:
            if not offer.wage and offer.applicant_id.salary_proposed:
                offer.wage = offer.applicant_id.salary_proposed

    @api.depends("applicant_id.partner_id")
    @api.depends_context("uid")
    def _compute_is_offer_for_current_user(self):
        # 仅当登录用户的 partner 与 applicant.partner_id 一致时为 True
        user_partner = self.env.user.partner_id
        for offer in self:
            applicant_partner = offer.applicant_id.partner_id
            offer.is_offer_for_current_user = bool(
                applicant_partner and applicant_partner == user_partner
            )

    @api.depends("contract_template_id.hr_responsible_id")
    def _compute_company_signer_id(self):
        # 默认从合同模板的 HR Responsible 取；用户可手动覆盖（公司变化重算覆盖手选）
        for offer in self:
            offer.company_signer_id = offer.contract_template_id.hr_responsible_id or False

    @api.depends("contract_template_id.resource_calendar_id")
    def _compute_working_time_text(self):
        for offer in self:
            calendar = offer.contract_template_id.resource_calendar_id
            attendances = calendar.attendance_ids if calendar else False
            if attendances:
                hour_from = min(attendances.mapped("hour_from"))
                hour_to = max(attendances.mapped("hour_to"))
                offer.working_time_text = "%s to %s" % (
                    self._format_hour(hour_from),
                    self._format_hour(hour_to),
                )
            else:
                offer.working_time_text = "9:30 to 18:30"

    @api.depends(
        "state",
        "sign_request_ids",
        "sign_request_ids.state",
        "sign_request_ids.request_item_ids.state",
        "sign_request_ids.request_item_ids.role_id.name",
    )
    def _compute_sign_request_state(self):
        # offer.state == 'full_signed' 兜底（覆盖电子签 + 线下签）；否则按 sign_request 实际状态算
        for offer in self:
            if offer.state == "full_signed":
                offer.has_sign_request = True
                offer.is_company_signed = True
                offer.is_employee_signed = True
                continue
            active = offer.sign_request_ids.filtered(
                lambda r: r.state not in ("canceled", "refused")
            )[:1]
            offer.has_sign_request = bool(active)
            if not active:
                offer.is_company_signed = False
                offer.is_employee_signed = False
                continue
            company_items = active.request_item_ids.filtered(
                lambda i: (i.role_id.name or "").strip().upper() == "COMPANY"
            )
            employee_items = active.request_item_ids - company_items
            offer.is_company_signed = bool(company_items) and all(
                i.state == "completed" for i in company_items
            )
            offer.is_employee_signed = bool(employee_items) and all(
                i.state == "completed" for i in employee_items
            )

    @staticmethod
    def _format_hour(value):
        # 0.5 -> "0:30", 9.0 -> "9:00", 18.5 -> "18:30"
        h = int(value)
        m = int(round((value - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return "%d:%02d" % (h, m)

    def action_open_refuse_wizard(self):
        """全部为 full_signed 时不打开 Refuse 向导；混合选中时仍可打开，仅非 full_signed 会被写入 refused。"""
        if self and not self.filtered(lambda o: o.state != "full_signed"):
            raise UserError(_("Fully signed offers cannot be refused."))
        return super().action_open_refuse_wizard()

    def action_refuse_offer(self, message=None, refusal_reason=None):
        """拒绝时跳过 full_signed（如候选人归档时顺带 refuse，不应把已签完 offer 标成 refused）。"""
        to_refuse = self.filtered(lambda o: o.state != "full_signed")
        if not to_refuse:
            return
        return super(HrContractSalaryOffer, to_refuse).action_refuse_offer(
            message=message, refusal_reason=refusal_reason
        )

    def action_open_sign_document(self):
        """打开候选人签署页面（手动流程）。"""
        sign_request, candidate_partner, company_partner = self._get_or_create_offer_sign_request()
        token = self._get_offer_signer_token(sign_request, candidate_partner, signer_kind="candidate")
        return {
            "type": "ir.actions.act_url",
            "url": f"/sign/document/{sign_request.id}/{token}",
            "target": "new",
        }

    def action_open_company_sign_document(self):
        """打开公司签署页面（手动流程）。"""
        self.ensure_one()
        sign_request, candidate_partner, company_partner = self._get_or_create_offer_sign_request()
        token = self._get_offer_signer_token(sign_request, company_partner, signer_kind="company")
        return {
            "type": "ir.actions.act_url",
            "url": f"/sign/document/{sign_request.id}/{token}",
            "target": "new",
        }

    def action_auto_sign_as_company(self):
        """[DEPRECATED] 自动完成公司签署。

        现行流程改为 HR 在 offer form 上手动点 "Company Sign" 进入签署页签字
        （见 action_open_company_sign_document），更安全可控。
        本方法及对应 view 按钮保留代码以备将来需要"一键签"场景时复活，
        但视图层永久 invisible="1"。请勿移除内部 SIGN_PREFILL_MAPPING 中
        date / signature 相关 key —— 它们仍被 _create_offer_sign_request 的
        text 字段预填逻辑共享。
        """
        self.ensure_one()
        sign_request, candidate_partner, company_partner = self._get_or_create_offer_sign_request()

        company_item = sign_request.request_item_ids.filtered(
            lambda r: (r.role_id.name or "").strip().upper() == "COMPANY"
        )[:1]
        if not company_item:
            raise UserError(_("No COMPANY role found in the sign request."))
        if company_item.state == "completed":
            raise UserError(_("The company has already signed this document."))

        Value = self.env["sign.request.item.value"].sudo()
        today_str = fields.Date.to_string(fields.Date.today())

        # 填 date 类型字段（如 SIGNATURE DATE）
        for item in sign_request.template_id.sign_item_ids.filtered(
            lambda i: i.responsible_id == company_item.role_id and i.type_id.item_type == "date"
        ):
            if Value.search_count([("sign_request_item_id", "=", company_item.id), ("sign_item_id", "=", item.id)]):
                continue
            key = (item.name or "").strip()
            value_str = str(self.SIGN_PREFILL_MAPPING[key](self)) if key in self.SIGN_PREFILL_MAPPING else today_str
            if not value_str:
                raise UserError(_("Cannot sign: the date field '%s' has no value.", item.name or "date"))
            Value.create({"sign_request_item_id": company_item.id, "sign_item_id": item.id, "value": value_str})

        # 填 signature 类型字段：用公司签署人在系统里保存的签名图片
        sig_items = sign_request.template_id.sign_item_ids.filtered(
            lambda i: i.responsible_id == company_item.role_id and i.type_id.item_type == "signature"
        )
        if sig_items:
            sig_bytes = company_item.sudo()._get_user_signature()
            if not sig_bytes:
                raise UserError(_(
                    "Cannot auto-sign: %s has no digital signature configured. "
                    "Please go to Settings → Profile (top-right avatar) and upload a signature image.",
                    company_item.partner_id.name,
                ))
            # Binary 字段返回的已经是 base64 字节，直接 decode 即可
            sig_b64 = sig_bytes.decode() if isinstance(sig_bytes, bytes) else sig_bytes
            sig_data_url = "data:image/png;base64,%s" % sig_b64
            # _fill() 第 409 行：self.signature = value[value.find(',') + 1:]  —— 只存逗号后的纯 base64
            company_item.sudo().signature = sig_b64
            for sig_item in sig_items:
                if not Value.search_count([("sign_request_item_id", "=", company_item.id), ("sign_item_id", "=", sig_item.id)]):
                    Value.create({"sign_request_item_id": company_item.id, "sign_item_id": sig_item.id, "value": sig_data_url})

        # 值已在创建时直接写入 DB，直接调 _post_fill_request_item() 完成签署
        # 避免 _sign()/_fill() 对 constant 字段调 write() 触发 readonly 报错
        company_item.sudo()._post_fill_request_item()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Company Signed"),
                "message": _("Document signed by the company. The candidate will receive an email with the signing link."),
                "type": "success",
                "sticky": False,
            },
        }

    def _get_or_create_offer_sign_request(self):
        """返回已有的活跃 sign request，否则创建新的。"""
        self.ensure_one()
        active = self.sign_request_ids.filtered(lambda r: r.state not in ("canceled", "refused"))[:1]
        if active:
            candidate_partner = self.applicant_id.partner_id
            company_partner = (self.company_signer_id.partner_id or self.env.user.partner_id)
            return active, candidate_partner, company_partner
        return self._create_offer_sign_request()

    def _get_offer_signer_token(self, sign_request, partner, signer_kind):
        self.ensure_one()
        def _is_company_role(sri):
            return (sri.role_id.name or "").strip().upper() == "COMPANY"

        if signer_kind == "company":
            request_item = sign_request.request_item_ids.filtered(lambda r: r.partner_id == partner and _is_company_role(r))[:1]
        else:
            request_item = sign_request.request_item_ids.filtered(lambda r: r.partner_id == partner and not _is_company_role(r))[:1]
        if not request_item:
            request_item = sign_request.request_item_ids.filtered(lambda r: r.partner_id == partner)[:1]
        return request_item.sudo().access_token or sign_request.request_item_ids[:1].sudo().access_token

    def _create_offer_sign_request(self):
        """创建并返回签署请求 + 两个签署人 partner。"""
        self.ensure_one()
        if not self.sign_template_id:
            raise UserError(_("Please set a PDF template (Sign Template) first."))

        required_text = {
            _("Employee Name"): self.applicant_id.partner_name,
            _("Position"): (self.employee_job_id.name or self.job_title),
            _("Department"): self.department_id.name if self.department_id else None,
            _("Reporting To"): self.reporting_to_id.name if self.reporting_to_id else None,
            _("Location"): self.work_location_id.name if self.work_location_id else None,
            _("Date of Joining"): self.contract_start_date,
            _("Company Name"): self.company_id.name if self.company_id else None,
        }
        missing = [label for label, val in required_text.items() if not val]
        if missing:
            raise UserError(_("Missing required information: %s", ", ".join(missing)))

        candidate_partner = self.applicant_id.partner_id
        if not candidate_partner:
            candidate_partner = self.env["res.partner"].create({
                "name": self.applicant_id.partner_name or _("Applicant"),
                "email": self.applicant_id.email_from,
                "phone": self.applicant_id.partner_phone,
                "company_id": self.company_id.id,
            })
            self.applicant_id.partner_id = candidate_partner
        if not candidate_partner.email:
            raise UserError(_("The applicant must have a valid email address to sign the document."))

        company_partner = self.company_signer_id.partner_id
        if not company_partner.email:
            raise UserError(_("The company signer must have a valid email address to sign the document."))

        template_roles = self.sign_template_id.sign_item_ids.responsible_id
        if template_roles:
            roles = template_roles
        else:
            roles = self.env.ref("sign.sign_item_role_default", raise_if_not_found=False)
            roles = roles or self.env["sign.item.role"]

        request_items_cmds = [
            Command.create({
                "role_id": role.id,
                "mail_sent_order": 1 if (role.name or "").strip().upper() == "COMPANY" else 2,
                "partner_id": company_partner.id if (role.name or "").strip().upper() == "COMPANY" else candidate_partner.id,
            })
            for role in roles
        ]
        if not request_items_cmds:
            raise UserError(_("The Sign Template has no roles."))

        sign_request = self.env["sign.request"].create({
            "template_id": self.sign_template_id.id,
            "request_item_ids": request_items_cmds,
            "reference": _("Offer - %s", self.display_name),
            "subject": _("Offer - %s", self.display_name),
            "reference_doc": f"{self._name},{self.id}",
        })
        self.sign_request_ids = [Command.link(sign_request.id)]

        # 直接 create 绕过 write() 的 constant 校验（_fill() 内部对已存在值调 write()，会触发 readonly 报错）
        Value = self.env["sign.request.item.value"].sudo()
        for item in sign_request.template_id.sign_item_ids.filtered(
            lambda i: i.type_id.item_type in ("text", "textarea", "selection", "strikethrough")
        ):
            key = (item.name or "").strip()
            if not key or key not in self.SIGN_PREFILL_MAPPING:
                continue
            raw_value = self.SIGN_PREFILL_MAPPING[key](self)
            if raw_value is False or raw_value is None:
                continue
            if isinstance(raw_value, (int, float)):
                value_str = str(raw_value)
            elif isinstance(raw_value, (datetime.date, datetime.datetime)):
                value_str = fields.Date.to_string(raw_value)
            else:
                value_str = str(raw_value)
            request_item = sign_request.request_item_ids.filtered(lambda r: r.role_id == item.responsible_id)[:1]
            if not request_item:
                continue
            Value.create({
                "sign_request_item_id": request_item.id,
                "sign_item_id": item.id,
                "value": value_str,
            })

        return sign_request, candidate_partner, company_partner

    def action_set_applicant_offered(self, is_ceo=False):
        """审批通过后：① 推进 applicant stage 到 Offered ② 发送 offer 邮件 ③ 静默创建 sign_request
        ④ 同步 onboarding 默认值到 applicant。
        manager 职位仅 CEO 通过时才执行（COO 通过时跳过，等 CEO）。
        """
        offered_stage = self.env.ref("tg_hr.hr_recruitment_stage_tg_offered", raise_if_not_found=False)
        for offer in self:
            applicant = offer.applicant_id
            if not applicant:
                continue
            if applicant.job_id.is_manager and not is_ceo:
                continue
            if offered_stage:
                applicant.stage_id = offered_stage
            offer._send_offer_email(silent_fail=True)
            # offer._create_sign_request_silently(silent_fail=True)
            offer._sync_applicant_onboarding_defaults()

    def _sync_applicant_onboarding_defaults(self):
        """审批通过后把 offer 上的关键字段同步到 applicant 的 onboarding 默认值。
        失败仅 chatter 留言（用户友好文案）+ log error，不阻塞其它流程。
        """
        self.ensure_one()
        applicant = self.applicant_id
        if not applicant:
            return
        try:
            vals = {}
            # salary_proposed: 仅当 applicant 端为 0/空时回填 offer.wage
            if not applicant.salary_proposed and self.wage:
                vals["salary_proposed"] = self.wage
            # ob_employee_type: 从合同模板（hr.version）的 employee_type 字段取，selection 完全兼容
            if self.contract_template_id and self.contract_template_id.employee_type:
                vals["ob_employee_type"] = self.contract_template_id.employee_type
            # ob_manager_id: 仅当 applicant 端为空时从 department.manager 兜底
            if (
                not applicant.ob_manager_id
                and applicant.department_id
                and applicant.department_id.manager_id
            ):
                vals["ob_manager_id"] = applicant.department_id.manager_id.id
            if vals:
                applicant.write(vals)
        except Exception:
            _logger.exception("Onboarding defaults sync failed for offer %s", self.id)
            try:
                self.message_post(body=_(
                    "Onboarding defaults sync failed. Please review the candidate's "
                    "onboarding fields manually."
                ))
            except Exception:
                _logger.exception("Failed to post sync-failure chatter for offer %s", self.id)

    def _create_sign_request_silently(self, silent_fail=True):
        """审批通过时静默创建 sign_request：用 no_sign_mail 抑制官方 sign 邀请邮件。
        失败仅 chatter 留言 + activity 提醒，不阻塞审批（silent_fail=True）。
        创建后流程：HR 在 offer form 上点 Company Sign 完成公司签 →
        点 Send Sign Link to Employee 邀请候选人。
        """
        self.ensure_one()
        # 已有活跃 sign_request 则跳过（幂等）
        if self.has_sign_request:
            return True
        try:
            self.with_context(no_sign_mail=True)._get_or_create_offer_sign_request()
        except UserError as e:
            self.message_post(body=_(
                "Failed to create sign request automatically: %s. "
                "Please fix the missing data and click [Recreate Sign Request] to retry.",
                e,
            ))
            try:
                responsible = (
                    (self.applicant_id and self.applicant_id.assigned_hr_id)
                    or self.create_uid
                    or self.env.user
                )
                self.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=responsible.id,
                    summary=_("Sign request creation failed — please fix and recreate"),
                    note=str(e),
                )
            except Exception:
                _logger.exception("Failed to schedule activity for sign request creation failure (offer %s)", self.id)
            if not silent_fail:
                raise
            return False
        return True

    # ── Tier Validation 字段白名单 ───────────────────────────────────────
    # OCA 的 view 改写用 _get_all_validation_exceptions（→ _get_validation_exceptions），
    # write 校验用 _get_under/after_validation_exceptions（也走 _get_validation_exceptions），
    # 所以只需 override 公共入口一次即可同时解除"只读"和"写入拦截"。
    _TIER_VALIDATION_EXTRA_FIELDS = [
        "email_template_id",
        "offer_sender_id",
        "company_signer_id",
        "offer_email_state",
        "offer_email_sent_date",
        # Sign 流程相关字段（审批通过后才能创建 sign / 发邀请，必须可写）
        "sign_request_ids",
        "sign_invite_sent_to_employee",
        "has_sign_request",
        "is_company_signed",
        "is_employee_signed",
        "sign_type",
        "offline_sign_note",
        # 原生字段：审批中/审批后仍允许变化（如拒绝、状态推进、create_employee 关联、跨公司迁移）
        "state",
        "refusal_reason",
        "refusal_date",
        "employee_id",
        "company_id",
    ]

    @api.model
    def _get_validation_exceptions(self, extra_domain=None, add_base_exceptions=True):
        res = super()._get_validation_exceptions(
            extra_domain=extra_domain, add_base_exceptions=add_base_exceptions
        )
        return list(set(res + self._TIER_VALIDATION_EXTRA_FIELDS))

    # ── Offer Email Sending ──────────────────────────────────────────────
    def _get_missing_offer_email_fields(self):
        """返回邮件渲染所需但当前缺失的字段 label 列表（空 list 表示就绪）。"""
        self.ensure_one()
        missing = []
        if not self.email_template_id:
            missing.append(_("Email Template"))
        if not self.applicant_id:
            missing.append(_("Applicant"))
        else:
            if not self.applicant_id.email_from:
                missing.append(_("Applicant Email"))
            if not self.applicant_id.partner_name:
                missing.append(_("Applicant Name"))
        if not (self.employee_job_id or self.job_title):
            missing.append(_("Job Title"))
        if not self.department_id:
            missing.append(_("Department"))
        if not self.work_location_id:
            missing.append(_("Work Location"))
        if not self.working_time_text:
            missing.append(_("Working Time"))
        if not self.reporting_to_id:
            missing.append(_("Reporting To"))
        if not self.contract_start_date:
            missing.append(_("Joining Date"))
        if not self.company_signer_id:
            missing.append(_("Company Signer"))
        if not self.offer_sender_id:
            missing.append(_("Offer Sender"))
        elif not self.offer_sender_id.work_email:
            missing.append(_("Offer Sender Work Email"))
        return missing

    def _handle_offer_email_failure(self, reason, silent_fail):
        """统一失败处理：chatter 留言 + activity + 状态置 failed。"""
        self.ensure_one()
        self.offer_email_state = "failed"
        body = _("Offer email NOT sent. Reason: %s", reason)
        self.message_post(body=body, message_type="comment")

        # 创建 activity 提醒 HR 处理
        responsible = (
            (self.applicant_id and self.applicant_id.assigned_hr_id)
            or self.create_uid
            or self.env.user
        )
        try:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=responsible.id,
                summary=_("Offer email failed — please fix and resend"),
                note=reason,
            )
        except Exception:
            _logger.exception("Failed to schedule activity for offer email failure (offer %s)", self.id)

        if not silent_fail:
            raise UserError(reason)
        return False

    def _send_offer_email(self, silent_fail=False):
        """发送 offer 邮件。silent_fail=True：失败仅留言+activity，不抛异常（自动场景）。"""
        self.ensure_one()
        missing = self._get_missing_offer_email_fields()
        if missing:
            return self._handle_offer_email_failure(
                _("Missing required information: %s", ", ".join(missing)),
                silent_fail,
            )

        try:
            mail_id = self.email_template_id.sudo().send_mail(
                self.id,
                force_send=True,
                email_layout_xmlid="mail.mail_notification_layout",
            )
        except Exception as e:
            _logger.exception("Offer email send_mail raised for offer %s", self.id)
            return self._handle_offer_email_failure(
                _("SMTP error: %s", e), silent_fail
            )

        mail = self.env["mail.mail"].sudo().browse(mail_id)
        if mail.exists() and mail.state == "exception":
            return self._handle_offer_email_failure(
                _("Mail server reported exception: %s", mail.failure_reason or _("unknown")),
                silent_fail,
            )

        self.offer_email_sent_date = fields.Datetime.now()
        self.offer_email_state = "sent"
        self.message_post(body=_(
            "Offer email dispatched to %s. Delivery confirmation depends on the recipient mail server.",
            self.applicant_id.email_from,
        ))
        return True

    # ── Sign 流程相关 actions ────────────────────────────────────────────
    def action_send_sign_link_to_employee(self):
        """给候选人发送 sign 邀请邮件（candidate 那条 request_item 的链接）。
        使用 sign 模块原生 send_signature_accesses，记录发送时间到
        sign_invite_sent_to_employee 字段。HR 可重复点击重发。
        """
        if not self.env.user.has_groups("tg_hr.group_hr_offer_email_sender,base.group_system"):
            raise UserError(_("You are not allowed to send sign invitations."))
        for offer in self:
            offer.ensure_one()
            if not offer.has_sign_request:
                raise UserError(_("No active sign request. Please create one first."))
            if not offer.is_company_signed:
                raise UserError(_("The company has not signed yet. Please complete the company side first."))

            active = offer.sign_request_ids.filtered(
                lambda r: r.state not in ("canceled", "refused")
            )[:1]
            employee_items = active.request_item_ids.filtered(
                lambda i: (i.role_id.name or "").strip().upper() != "COMPANY"
            )
            if not employee_items:
                raise UserError(_("No candidate signer found in the sign request."))
            employee_items.send_signature_accesses()
            offer.sign_invite_sent_to_employee = fields.Datetime.now()
            offer.message_post(body=_(
                "Sign invitation sent to candidate(s): %s",
                ", ".join(employee_items.mapped("partner_id.name")),
            ))
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    def action_mark_employee_signed_offline(self):
        """打开 wizard 让 HR 上传线下签好的纸质合同扫描件，标记员工已线下签。"""
        self.ensure_one()
        if not self.env.user.has_groups("tg_hr.group_hr_offer_email_sender,base.group_system"):
            raise UserError(_("You are not allowed to mark offer as signed offline."))
        return {
            "name": _("Mark Employee Signed Offline"),
            "type": "ir.actions.act_window",
            "res_model": "hr.offer.mark.signed.offline.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_offer_id": self.id},
        }

    def action_recreate_sign_request(self):
        """取消所有现有 sign_request 后重建
        旧 sign_request 不删除，cancel 后保留作为历史记录。
        """
        if not self.env.user.has_groups("tg_hr.group_hr_offer_email_sender,base.group_system"):
            raise UserError(_("You are not allowed to recreate sign requests."))
        for offer in self:
            offer.ensure_one()
            # cancel 所有未结束的旧 sign_request（保留记录，不 unlink）
            active = offer.sign_request_ids.filtered(
                lambda r: r.state not in ("canceled", "refused", "signed")
            )
            for old in active:
                try:
                    old.cancel()
                except Exception:
                    _logger.exception("Failed to cancel old sign request %s for offer %s", old.id, offer.id)
            # 强制重新创建（不抑制邮件 —— 手动重建场景下用户预期看到行为）
            offer.with_context(no_sign_mail=True)._create_offer_sign_request()
            offer.message_post(body=_("Sign request recreated."))
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    # ── Stage 推进 hook ──────────────────────────────────────────────────
    def write(self, vals):
        # 监听 offer.state 从其他变 'full_signed'：推进 applicant 和 requisition stage。
        # offer.state 由 hr_contract_salary 官方 controller 在候选人完成签署时写入。
        trigger_offers = self.env["hr.contract.salary.offer"]
        if vals.get("state") == "full_signed":
            trigger_offers = self.filtered(lambda o: o.state != "full_signed")
        res = super().write(vals)
        for offer in trigger_offers:
            offer._on_offer_fully_signed()
        return res

    def _on_offer_fully_signed(self):
        """全部签署完成时推进相关 stage。"""
        self.ensure_one()
        contract_signed_stage = self.env.ref("hr_recruitment.stage_job5", raise_if_not_found=False)
        hired_stage = self.env.ref("tg_hr.requisition_stage_hired", raise_if_not_found=False)

        applicant = self.applicant_id
        if applicant and contract_signed_stage:
            applicant.sudo().stage_id = contract_signed_stage

        requisition = applicant and getattr(applicant, "requisition_id", False)
        if requisition and hired_stage:
            requisition.sudo().stage_id = hired_stage

        # sign_type 兜底：wizard 已经设过则不动；否则视为电子签自动完成
        if not self.sign_type:
            self.sudo().sign_type = "online"

        self.message_post(body=_("Offer fully signed — applicant and requisition stages advanced."))

    def action_send_offer_email(self):
        """手动发送/重发 offer 邮件按钮。失败抛 UserError 触发前端 notification。

        注意：当前按钮单选触发；如果未来要改成多选/批量，需要在循环里独立 try/except，
        否则中途某条失败会触发事务回滚——前面已 SMTP 投递的邮件无法回滚，但
        offer_email_sent_date / state 等数据库字段会被 rollback，造成"邮件发了但
        DB 显示未发"的脏状态。
        """
        if not self.env.user.has_groups("tg_hr.group_hr_offer_email_sender,base.group_system"):
            raise UserError(_("You are not allowed to send offer emails."))
        for offer in self:
            offer._send_offer_email(silent_fail=False)
        return {"type": "ir.actions.client", "tag": "soft_reload"}

    @api.model
    def _cron_notify_offer_start_t3(self):
        today = fields.Date.context_today(self)
        target_date = today + timedelta(days=3)

        offers = self.search([
            ('approval_state', '=', 'approved'),
            ('state', '!=', 'refused'),
            ('contract_start_date', '<=', target_date),
            ('applicant_id', '!=', False),
        ], order='applicant_id asc, id desc')

        # 每个 applicant 只取最新一条 offer，去重
        seen_applicants = set()
        applicants = []
        for offer in offers:
            if offer.applicant_id.id not in seen_applicants:
                seen_applicants.add(offer.applicant_id.id)
                # 只有未采集完成的需要通知
                if not offer.applicant_id.onboarding_complete:
                    applicants.append(offer.applicant_id)

        # 按 assigned_hr_id 分组，每个 HR 只发一封
        hr_map = {}
        for applicant in applicants:
            hr = applicant.assigned_hr_id
            if hr and hr.email:
                hr_map.setdefault(hr, []).append(applicant)

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for hr_user, hr_applicants in hr_map.items():
            self.env['mail.mail'].sudo().create({
                'subject': f'[T-3 Reminder] {len(hr_applicants)} applicant(s) joining on {target_date}',
                'email_to': hr_user.email,
                'body_html': self._build_t3_email_body(hr_user, hr_applicants, target_date, base_url),
                'auto_delete': True,
            }).send()

    def _build_t3_email_body(self, hr_user, applicants, target_date, base_url):
        rows = ''
        for a in applicants:
            url = f'{base_url}/web#model=hr.applicant&id={a.id}&view_type=form'
            rows += (
                f'<tr>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">'
                f'<a href="{url}" style="color:#017e84;text-decoration:none;font-weight:500;">{a.partner_name}</a>'
                f'</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">{a.job_id.name or ""}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #eee;">{a.department_id.name or ""}</td>'
                f'</tr>'
            )
        return (
            f'<p>Hi <strong>{hr_user.name}</strong>,</p>'
            f'<p>The following applicant(s) are scheduled to join on '
            f'<strong>{target_date}</strong> (3 days from now). '
            f'Please ensure all pre-joining steps are completed.</p>'
            f'<table style="border-collapse:collapse;width:100%;font-size:14px;">'
            f'<thead><tr style="background:#f5f5f5;">'
            f'<th style="padding:8px 12px;text-align:left;">Applicant</th>'
            f'<th style="padding:8px 12px;text-align:left;">Position</th>'
            f'<th style="padding:8px 12px;text-align:left;">Department</th>'
            f'</tr></thead>'
            f'<tbody>{rows}</tbody>'
            f'</table>'
            f'<p style="margin-top:16px;color:#888;font-size:12px;">Automated reminder — HR System</p>'
        )
