# -*- coding: utf-8 -*-
import datetime

from odoo import _, api, fields, models, Command
from odoo.exceptions import UserError


class HrContractSalaryOffer(models.Model):
    _name = "hr.contract.salary.offer"
    _inherit = ["hr.contract.salary.offer", "tier.validation.zb"]

    _tier_validation_manual_config = False

    reporting_to_id = fields.Many2one("hr.employee", string="Reporting To", required=True)
    work_location = fields.Char(string="Location", required=True)

    basic_salary = fields.Monetary(string="Basic Salary", required=True, default=0.0, currency_field="currency_id")
    house_rent_allowance = fields.Monetary(string="House Rent Allowance", required=True, default=0.0, currency_field="currency_id")
    medical_allowance = fields.Monetary(string="Medical Allowance", required=True, default=0.0, currency_field="currency_id")
    conveyance_allowance = fields.Monetary(string="Conveyance Allowance", required=True, default=0.0, currency_field="currency_id")

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
