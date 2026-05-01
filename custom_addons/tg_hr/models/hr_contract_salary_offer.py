# -*- coding: utf-8 -*-
import datetime
import logging
from datetime import timedelta

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrContractSalaryOffer(models.Model):
    _name = "hr.contract.salary.offer"
    _inherit = ["hr.contract.salary.offer", "tier.validation.zb"]

    _tier_validation_manual_config = False

    reporting_to_id = fields.Many2one("hr.employee", string="Reporting To", required=True, tracking=True)
    work_location = fields.Char(string="Location", required=True, tracking=True)

    wage = fields.Monetary(string="Wage", required=True, default=0.0, currency_field="currency_id", tracking=True)
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
        help="Working hours text shown in the offer email, e.g. '9:30 to 18:30'.",
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

    SIGN_PREFILL_MAPPING = {
        "EMPLOYEE NAME": lambda o: o.applicant_id.partner_name or "",
        "POSITION": lambda o: o.employee_job_id.name or o.job_title or "",
        "DEPARTMENT": lambda o: o.department_id.name or "",
        "POSITION & DEPARTMENT": lambda o: " / ".join(filter(None, [
            o.employee_job_id.name or o.job_title or "",
            o.department_id.name or "",
        ])),
        "REPORTING TO": lambda o: o.reporting_to_id.name or "",
        "LOCATION": lambda o: o.work_location or "",
        "JOB LOCATION": lambda o: o.work_location or "",
        "DATE OF JOINING": lambda o: o.contract_start_date or "",
        "DATE OF JOING": lambda o: o.contract_start_date or "",
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
            offer.basic_salary_upper_zh = offer._amount_to_chinese_upper(offer.basic_salary or 0.0)

    @api.depends("company_id")
    def _compute_email_template_id(self):
        # 根据公司挑选默认 offer 邮件模板：模板 company_ids 包含当前公司即匹配
        Template = self.env["mail.template"].sudo()
        for offer in self:
            if offer.email_template_id:
                continue
            if not offer.company_id:
                offer.email_template_id = False
                continue
            tmpl = Template.search(
                [
                    ("model", "=", "hr.contract.salary.offer"),
                    ("company_ids", "in", offer.company_id.id),
                ],
                limit=1,
            )
            offer.email_template_id = tmpl or False

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

    @staticmethod
    def _format_hour(value):
        # 0.5 -> "0:30", 9.0 -> "9:00", 18.5 -> "18:30"
        h = int(value)
        m = int(round((value - h) * 60))
        if m == 60:
            h += 1
            m = 0
        return "%d:%02d" % (h, m)

    def _amount_to_chinese_upper(self, amount):
        """将金额转中文大写（人民币格式：元/角/分）。"""
        # 仅用于展示与预填，非会计核算；简化实现满足合同模板场景。
        cn_num = "零壹贰叁肆伍陆柒捌玖"
        cn_unit = ["", "拾", "佰", "仟"]
        cn_group = ["", "万", "亿", "兆"]
        amount = round(float(amount or 0.0), 2)
        if amount == 0:
            return "零元整"
        sign = "负" if amount < 0 else ""
        amount = abs(amount)
        integer = int(amount)
        fraction = int(round((amount - integer) * 100))
        jiao = fraction // 10
        fen = fraction % 10

        def _four_to_cn(n):
            s = ""
            zero = False
            for i in range(4):
                d = n % 10
                if d == 0:
                    if not zero and s:
                        s = cn_num[0] + s
                    zero = True
                else:
                    s = cn_num[d] + cn_unit[i] + s
                    zero = False
                n //= 10
            return s.strip(cn_num[0])

        groups = []
        g_idx = 0
        while integer > 0:
            part = integer % 10000
            if part:
                part_cn = _four_to_cn(part)
                if part_cn:
                    groups.insert(0, part_cn + cn_group[g_idx])
            else:
                groups.insert(0, "")
            integer //= 10000
            g_idx += 1

        int_cn = "".join([g for g in groups if g])
        # 处理中间断层的零（简化：用正则压缩多个零）
        int_cn = int_cn.replace("零零", "零")
        int_cn = int_cn.rstrip("零")
        int_cn = int_cn or cn_num[0]
        result = sign + int_cn + "元"

        if jiao == 0 and fen == 0:
            return result + "整"
        if jiao:
            result += cn_num[jiao] + "角"
        elif fen:
            result += "零"
        if fen:
            result += cn_num[fen] + "分"
        return result

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
        """自动完成公司签署，然后候选人可通过邮件链接查看并签署。"""
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
            import base64 as _b64
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
            company_partner = (self.contract_template_id.hr_responsible_id.partner_id or self.env.user.partner_id)
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
            _("Location"): self.work_location,
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

        company_partner = (self.contract_template_id.hr_responsible_id.partner_id or self.env.user.partner_id)
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
        """审批通过后：① 推进 applicant stage 到 Offered ② 自动发送 offer 邮件。
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

    # ── Tier Validation 字段白名单 ───────────────────────────────────────
    # OCA 的 view 改写用 _get_all_validation_exceptions（→ _get_validation_exceptions），
    # write 校验用 _get_under/after_validation_exceptions（也走 _get_validation_exceptions），
    # 所以只需 override 公共入口一次即可同时解除"只读"和"写入拦截"。
    _TIER_VALIDATION_EXTRA_FIELDS = [
        "email_template_id",
        "offer_email_state",
        "offer_email_sent_date",
        # 原生字段：审批中/审批后仍允许变化（如拒绝、状态推进）
        "state",
        "refusal_reason",
        "refusal_date",
    ]

    @api.model
    def _get_validation_exceptions(self, extra_domain=None, add_base_exceptions=True):
        res = super()._get_validation_exceptions(
            extra_domain=extra_domain, add_base_exceptions=add_base_exceptions
        )
        return list(set(res + self._TIER_VALIDATION_EXTRA_FIELDS))

    # ── Offer Email Sending ──────────────────────────────────────────────
    def _check_offer_email_ready(self):
        """检查 offer 邮件渲染所需字段是否齐全。返回缺失字段的 label 列表。"""
        self.ensure_one()
        missing = []
        if not self.email_template_id:
            missing.append(_("Email Template"))
        if not self.applicant_id or not self.applicant_id.email_from:
            missing.append(_("Applicant Email"))
        if not (self.employee_job_id or self.job_title):
            missing.append(_("Job Title"))
        if not self.department_id:
            missing.append(_("Department"))
        if not self.work_location:
            missing.append(_("Work Location"))
        if not self.working_time_text:
            missing.append(_("Working Time"))
        if not self.reporting_to_id:
            missing.append(_("Reporting To"))
        if not self.contract_start_date:
            missing.append(_("Joining Date"))
        if not (self.contract_template_id and self.contract_template_id.hr_responsible_id):
            missing.append(_("HR Responsible (signer)"))
        if not (self.applicant_id and self.applicant_id.partner_name):
            missing.append(_("Applicant Name"))
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
        missing = self._check_offer_email_ready()
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

    def action_send_offer_email(self):
        """手动发送/重发 offer 邮件按钮。失败抛 UserError 触发前端 notification。"""
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
