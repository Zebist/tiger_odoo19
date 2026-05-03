# -*- coding: utf-8 -*-
import logging
import re
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# TB = Tiger Battery (Bangladesh), TL = Tiger Lithium (Bangladesh)
_BD_REGIONS = ('tb', 'tl')

# NID: Smart ID 10 位 / Analog ID 17 位
_BD_NID_RE = re.compile(r'^\d{10}$|^\d{17}$')
# 银行卡：DBBL=11, BRAC/Dhaka Bank=13, IBBL=17
_BD_BANK_RE = re.compile(r'^\d{11}$|^\d{13}$|^\d{17}$')

# 中国身份证：17位数字 + 数字或大写X
_CN_ID_RE = re.compile(r'^\d{17}[\dX]$')
# 中国护照：E+8位数字（旧版）或 E+1位字母(非I/O)+7位数字（新版）
_CN_PASSPORT_RE = re.compile(r'^E\d{8}$|^E[A-HJ-NP-Z]\d{7}$')
# 银联银行卡：16-19位数字
_CN_BANK_RE = re.compile(r'^\d{16,19}$')

# 手机号（本地号码）：BD/CN = 11 位，SG = 8 位
_PHONE_11_RE = re.compile(r'^\d{11}$')
_PHONE_8_RE = re.compile(r'^\d{8}$')

# 所有 checklist 项（与 onboarding_progress 计算保持同步）
_ALWAYS_CHK = [
    'chk_personal_info',
    'chk_id_info',
    'chk_id_documents',
    'chk_bank_info',
    'chk_contract_info',
    'chk_diploma',
    'chk_resignation_proof',
]
_COND_CHK = {
    'chk_tax_info': lambda r: r.ob_region in ('tb', 'tl'),
    'chk_expat_info': lambda r: r.ob_position_type == 'expat',
    'chk_safety_training': lambda r: r.ob_position_type == 'factory',
}


class HrApplicant(models.Model):
    _inherit = ["hr.applicant", "form.readonly.mixin"]

    _STAGE_SEQUENCE = [
        "hr_recruitment.stage_job0",  # new
        "tg_hr.hr_recruitment_stage_tg_initital",  # init
        "tg_hr.hr_recruitment_stage_tg_contacted",  # contacted
        "tg_hr.hr_recruitment_stage_tg_interview",  # interview
        "tg_hr.hr_recruitment_stage_tg_offered",  # offered
        "hr_recruitment.stage_job5",  # contract signed (hr_recruitment.stage_job5)
    ]

    # 进入该阶段前必须满足的字段条件，后续阶段会累积检查前面所有阶段的条件
    _STAGE_ENTRY_REQUIREMENTS = {
        "tg_hr.hr_recruitment_stage_tg_contacted": [
            ("resume_reviewed", "Resume Review"),
            ("first_contact_made", "First Contact"),
        ],
        "tg_hr.hr_recruitment_stage_tg_interview": [
            ("interview_type", "Set Interview"),
        ],
        "tg_hr.hr_recruitment_stage_tg_offered": [
            ("interview_passed", "Interview Passed"),
        ],
        "hr_recruitment.stage_job5": [
            ("latest_approved_offer_fully_signed", "Offer Fully Signed"),
        ],
    }

    stage_id = fields.Many2one(default=lambda r: r.env.ref('hr_recruitment.stage_job0', raise_if_not_found=False))
    is_contract_signed_stage = fields.Boolean(
        string="Is Contract Signed",
        compute="_compute_is_contract_signed_stage",
        store=True,
        help="True when applicant.stage_id is the Contract Signed stage (hr_recruitment.stage_job5).",
    )
    # New → Initial Screening 一键推进（仅 New 阶段展示，人才库候选人除外）
    show_move_to_initial_screening_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_review_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_first_contact_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_interview_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    show_pass_interview_button = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 是否处于 Interview 阶段（控制面试分组显隐）
    is_in_interview_stage = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 是否处于 Offered 阶段（与 is_in_interview_stage 对称，用于按钮显隐）
    is_in_offered_stage = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 非 New 阶段时为 True（控制 Interview Process 页显隐）
    show_interview_process_page = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 处于 Offered 阶段时为 True（控制 Onboarding Preparation 页显隐）
    show_onboarding_page = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )
    # 是否存在未被拒绝的 offer（用于控制 Create Offer 按钮显隐）
    has_active_offer = fields.Boolean(
        compute="_compute_tg_hr_stage_flags",
        compute_sudo=True,
        store=False,
    )

    requisition_id = fields.Many2one(
        "tg.hr.requisition",
        string="Requisition",
        tracking=True,
        ondelete="set null",
    )

    priority = fields.Selection(
        selection=[
            ("0", "Not Rated"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        default="0",
        tracking=True,
        string="Initial Screening Score"
    )

    resume_reviewed = fields.Boolean(string="Resume Reviewed", default=False, tracking=True, compute='_compute_resume_reviewd', readonly=True, compute_sudo=True, store=True)
    review_date = fields.Date(string="Review Date", tracking=True)
    initial_screening_notes = fields.Html(string="Initial Screening Notes", tracking=True)

    first_contact_made = fields.Boolean(string="First Contact Made", default=False, tracking=True, compute='_compute_first_contact_made', readonly=True, compute_sudo=True, store=True)
    first_contact_date = fields.Date(string="First Contact Date", tracking=True)

    interview_passed = fields.Boolean(
        string="Interview Passed",
        default=False,
        tracking=True,
    )
    # 与 _get_latest_approved_offer 一致：按 id 最新一条且已审批、未拒绝时，是否已 full_signed
    latest_approved_offer_fully_signed = fields.Boolean(
        string="Latest Approved Offer Fully Signed",
        compute="_compute_latest_approved_offer_fully_signed",
        compute_sudo=True,
        store=True,
        help="True when the newest salary offer (by id) is approved, not refused, and fully signed.",
    )

    interview_score = fields.Selection(
        selection=[
            ("0", "Not Rated"),
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
        ],
        string="Interview Score",
        default="0",
        tracking=True,
    )
    interview_datetime = fields.Datetime(string="Interview Date & Time", tracking=True)
    interview_type = fields.Selection(
        selection=[
            ("online", "Online"),
            ("offline", "Offline"),
        ],
        string="Interview Type",
        tracking=True,
    )
    meeting_url = fields.Char(string="Meeting URL", tracking=True)
    interview_notes = fields.Html(string="Interview Notes", tracking=True)

    assigned_hr_id = fields.Many2one(
        "res.users",
        string="Assigned HR",
        default=lambda self: self.env.user,
        tracking=True,
        domain=[("share", "=", False)],
    )

    # ── Onboarding: 区域 & 岗位类别 ──────────────────────────────────────
    ob_region = fields.Selection(
        [('sg', 'Singapore (SG)'), ('cn', 'China (CN)'), ('tb', 'Bangladesh (TB)'), ('tl', 'Bangladesh (TL)')],
        string='Region', tracking=True,
    )
    ob_position_type = fields.Selection(
        [('normal', 'Normal'), ('expat', 'Expat'), ('factory', 'Factory')],
        string='Position Type', tracking=True,
    )

    # ── Onboarding: 个人基本信息 ──────────────────────────────────────────
    local_name = fields.Char(
        string='Local Name',
        tracking=True,
        help="Optional. The applicant's legal/official name in their local language or script "
             "(e.g. Chinese, Bengali). Synced to employee.legal_name on hire.",
    )
    work_location_id = fields.Many2one(
        'hr.work.location',
        string='Work Location',
        tracking=True,
        domain="[('company_id', 'in', [False, company_id])]",
    )
    ob_sex = fields.Selection(
        [('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        string='Gender', tracking=True,
    )
    ob_birthday = fields.Date(string='Date of Birth', tracking=True)
    ob_nationality_id = fields.Many2one('res.country', string='Nationality', tracking=True,
                                        options="{'no_quick_create': True}")
    ob_emergency_contact = fields.Char(string='Emergency Contact', tracking=True)
    ob_emergency_phone = fields.Char(string='Emergency Phone', tracking=True)

    # ── Onboarding: 证件信息 ──────────────────────────────────────────────
    ob_identification_id = fields.Char(string='National ID (NID)', tracking=True)
    ob_passport_id = fields.Char(string='Passport No', tracking=True)
    ob_passport_expiration_date = fields.Date(string='Passport Expiry', tracking=True)

    # ── Onboarding: 银行信息（文本，Create Employee 时转关联）────────────
    ob_bank_name = fields.Char(string='Bank Name', tracking=True)
    ob_bank_account_number = fields.Char(string='Bank Account Number', tracking=True)
    ob_bank_account_holder = fields.Char(string='Account Holder', tracking=True)
    ob_swift_code = fields.Char(string='Swift Code', tracking=True)

    # ── Onboarding: 税务 ──────────────────────────────────────────────────
    ob_tin_number = fields.Char(string='TIN (Tax ID)', tracking=True)

    # ── Onboarding: 合同信息 ──────────────────────────────────────────────
    ob_employee_type = fields.Selection(
        [('employee', 'Employee'), ('worker', 'Worker'), ('student', 'Student'),
         ('trainee', 'Trainee'), ('contractor', 'Contractor'), ('freelance', 'Freelancer')],
        string='Employment Type', tracking=True
    )
    ob_manager_id = fields.Many2one('hr.employee', string='Reporting Manager', tracking=True,
                                    options="{'no_quick_create': True}")
    ob_trial_period_months = fields.Integer(string='Trial Period (Months)', tracking=True, default=6)

    # ── Onboarding: 外派专项（position_type == expat）────────────────────
    ob_visa_no = fields.Char(string='Visa No', tracking=True)
    ob_visa_expire = fields.Date(string='Visa Expiry', tracking=True)
    ob_work_permit_expiration_date = fields.Date(string='Work Permit Expiry', tracking=True)

    # ── Onboarding: 工厂专项（position_type == factory）──────────────────
    ob_safety_training_notes = fields.Text(string='Safety Training Notes', tracking=True)
    ob_safety_training_confirmed = fields.Boolean(
        string='Safety Training Confirmed',
        compute='_compute_ob_safety_training_confirmed',
        store=True,
    )

    # ── Onboarding: 附件明细 ──────────────────────────────────────────────
    onboarding_attachment_ids = fields.One2many(
        'tg.hr.applicant.attachment', 'applicant_id', string='Onboarding Documents',
    )

    # ── Checklist（全 compute + store，全部 True 时 onboarding_complete）──
    chk_personal_info = fields.Boolean(string='Personal Info', compute='_compute_chk_personal_info', store=True)
    chk_id_info = fields.Boolean(string='ID Info', compute='_compute_chk_id_info', store=True)
    chk_id_documents = fields.Boolean(string='ID Scan', compute='_compute_chk_id_documents', store=True)
    chk_bank_info = fields.Boolean(string='Bank Info', compute='_compute_chk_bank_info', store=True)
    chk_tax_info = fields.Boolean(string='Tax Info', compute='_compute_chk_tax_info', store=True)
    chk_contract_info = fields.Boolean(string='Contract Info', compute='_compute_chk_contract_info', store=True)
    chk_diploma = fields.Boolean(string='Diploma', compute='_compute_chk_diploma', store=True)
    chk_resignation_proof = fields.Boolean(string='Resignation Proof', compute='_compute_chk_resignation_proof', store=True)
    chk_expat_info = fields.Boolean(string='Expat Info', compute='_compute_chk_expat_info', store=True)
    chk_safety_training = fields.Boolean(string='Safety Training', compute='_compute_chk_safety_training', store=True)

    onboarding_done_count = fields.Integer(compute='_compute_onboarding_progress', store=True)
    onboarding_total_count = fields.Integer(compute='_compute_onboarding_progress', store=True)
    onboarding_progress = fields.Float(string='Onboarding Progress (%)', compute='_compute_onboarding_progress', store=True)
    onboarding_complete = fields.Boolean(string='Onboarding Complete', compute='_compute_onboarding_progress', store=True)

    # ─────────────────────────────────────────────────────────────────────
    # Compute: 既有字段（原代码保留）
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('review_date')
    def _compute_resume_reviewd(self):
        for rec in self:
            rec.resume_reviewed = bool(rec.review_date)

    @api.depends('first_contact_date')
    def _compute_first_contact_made(self):
        for rec in self:
            rec.first_contact_made = bool(rec.first_contact_date)

    def _can_review(self):
        """Reviewer rule: assigned_hr empty → anyone may review;
        otherwise only the assigned HR (or recruitment managers) may review."""
        self.ensure_one()
        if self.env.user.has_group("hr_recruitment.group_hr_recruitment_manager"):
            return True
        if not self.assigned_hr_id:
            return True
        return self.assigned_hr_id.id == self.env.uid

    def _get_latest_approved_offer(self):
        """按 id 降序取最新一条 salary offer；仅当该条已审批通过且未拒绝时返回，否则返回空记录集。"""
        self.ensure_one()
        latest = self.salary_offer_ids.sorted("id", reverse=True)[:1]
        if (
            latest
            and latest.approval_state == "approved"
            and latest.state != "refused"
        ):
            return latest
        return self.env["hr.contract.salary.offer"]

    @api.depends(
        "salary_offer_ids",
        "salary_offer_ids.approval_state",
        "salary_offer_ids.state",
    )
    def _compute_latest_approved_offer_fully_signed(self):
        for rec in self:
            offer = rec._get_latest_approved_offer()
            rec.latest_approved_offer_fully_signed = bool(offer) and offer.state == "full_signed"

    @api.depends(
        "stage_id",
        "resume_reviewed",
        "first_contact_made",
        "interview_passed",
        "assigned_hr_id",
        "salary_offer_ids.approval_state",
        "salary_offer_ids.state",
        "is_pool_applicant",
        "talent_pool_ids",
    )
    def _compute_tg_hr_stage_flags(self):
        init_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_initital", raise_if_not_found=False
        )
        init_stage_id = init_stage if init_stage else False
        contacted_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_contacted", raise_if_not_found=False
        )
        contacted_stage_id = contacted_stage if contacted_stage else False
        interview_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_interview", raise_if_not_found=False
        )
        interview_stage_id = interview_stage if interview_stage else False
        # Odoo 内置的 New 阶段，用于判断是否隐藏 Interview Process 页
        new_stage = self.env.ref(
            "hr_recruitment.stage_job0", raise_if_not_found=False
        )
        new_stage_id = new_stage if new_stage else False
        offered_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_offered", raise_if_not_found=False
        )
        offered_stage_id = offered_stage if offered_stage else False
        contract_signed_stage = self.env.ref(
            "hr_recruitment.stage_job5", raise_if_not_found=False
        )
        contract_signed_stage_id = contract_signed_stage if contract_signed_stage else False
        for applicant in self:
            stage_id = applicant.stage_id
            applicant.show_move_to_initial_screening_button = bool(
                new_stage_id
                and stage_id == new_stage_id
                and not applicant.is_pool_applicant
            )
            applicant.show_review_button = bool(
                stage_id == init_stage_id
                and not applicant.resume_reviewed
                and applicant._can_review()
            )
            applicant.show_first_contact_button = bool(stage_id == init_stage_id and applicant.resume_reviewed)
            applicant.show_interview_button = bool(stage_id == contacted_stage_id and applicant.first_contact_made)
            applicant.is_in_interview_stage = bool(stage_id == interview_stage_id)
            applicant.is_in_offered_stage = bool(stage_id == offered_stage_id)
            applicant.show_pass_interview_button = bool(stage_id == interview_stage_id and not applicant.interview_passed)
            # 有阶段且不是 New 阶段时显示 Interview Process 页
            applicant.show_interview_process_page = bool(stage_id and stage_id != new_stage_id)
            # Offered 或 Contract Signed 阶段且「按 id 最新且已审批未拒绝」的 offer 存在时显示 Onboarding Preparation 页
            offer_approved = bool(applicant._get_latest_approved_offer())
            applicant.show_onboarding_page = bool(
                stage_id in (offered_stage_id, contract_signed_stage_id) and offer_approved
            )
            applicant.has_active_offer = any(o.state != 'refused' for o in applicant.salary_offer_ids)

    @api.depends("stage_id")
    def _compute_is_contract_signed_stage(self):
        target = self.env.ref("hr_recruitment.stage_job5", raise_if_not_found=False)
        for applicant in self:
            applicant.is_contract_signed_stage = bool(target) and applicant.stage_id == target

    def write(self, vals):
        # 锁定 Contract Signed stage：进入此阶段后不允许再改 stage_id（kanban 拖拽 / form 切换都拦截）。
        # 拥有「Applicant Contract Signed Stage Override」组的用户可绕过（由 HR 管理员按需分配）。
        if "stage_id" in vals and not self.env.user.has_group(
            "tg_hr.group_hr_applicant_contract_signed_stage_override"
        ):
            target = self.env.ref("hr_recruitment.stage_job5", raise_if_not_found=False)
            if target and vals["stage_id"] != target.id:
                locked = self.filtered(lambda r: r.stage_id == target)
                if locked:
                    raise UserError(_(
                        "Applicant(s) %s are in 'Contract Signed' stage and cannot be moved to another stage. "
                        ", ".join(locked.mapped("partner_name")),
                    ))
        return super().write(vals)

    # ── form.readonly.mixin 接入：Contract Signed stage 整体只读，
    #    仅 onboarding page (name="tg_hr_onboarding") 内字段保持可编辑 ──
    def _get_view_readonly_expr(self):
        return "is_contract_signed_stage"

    def _get_view_readonly_depends(self):
        return ("is_contract_signed_stage",)

    def _get_view_readonly_skip_containers(self):
        return ("tg_hr_onboarding",)

    def action_show_offers(self):
        """与表单 stat 按钮 groups 一致；系统用户 sudo，其余走 ACL + record rule。"""
        if not self.env.user.has_groups(
            "hr_recruitment.group_hr_recruitment_user,"
            "tg_hr.group_hr_offer_email_sender,base.group_system"
        ):
            raise AccessError(_("You are not allowed to open salary offers for applicants."))
        if self.env.user.has_group("base.group_system"):
            self = self.sudo()
        return super(HrApplicant, self).action_show_offers()

    def action_move_to_initial_screening(self):
        """从 New 阶段进入 Initial Screening（与 statusbar 下一阶段一致）。"""
        new_stage = self.env.ref("hr_recruitment.stage_job0", raise_if_not_found=False)
        init_stage = self.env.ref("tg_hr.hr_recruitment_stage_tg_initital", raise_if_not_found=False)
        if not init_stage:
            raise UserError(_("Initial screening stage is not configured (missing xml id tg_hr.hr_recruitment_stage_tg_initital)."))
        if not new_stage:
            raise UserError(_("New stage is not configured (missing xml id hr_recruitment.stage_job0)."))
        invalid = self.filtered(lambda a: a.stage_id != new_stage or a.is_pool_applicant)
        if invalid:
            raise UserError(
                _("This action only applies to job applicants in the New stage (not talent pool). Records: %s")
                % ", ".join(invalid.mapped("display_name"))
            )
        self.write({"stage_id": init_stage.id})
        return True

    def action_open_review_wizard(self):
        self.ensure_one()
        if not self._can_review():
            raise UserError(_(
                "Only the assigned HR (%s) can review this applicant."
            ) % (self.assigned_hr_id.name or "-"))
        return {
            "name": self.env._("Resume Review"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
                "default_review_date": fields.Date.context_today(self),
                "default_resume_reviewed": True,
                "default_priority": self.priority,
            },
        }

    def action_open_first_contact_wizard(self):
        self.ensure_one()
        return {
            "name": self.env._("First Contact"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.first.contact.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
                "default_first_contact_date": fields.Date.context_today(self),
                "default_first_contact_made": True,
            },
        }

    def action_open_interview_wizard(self):
        self.ensure_one()
        return {
            "name": self.env._("Interview Details"),
            "type": "ir.actions.act_window",
            "res_model": "tg.hr.applicant.interview.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_applicant_id": self.id,
            },
        }

    def action_pass_interview(self):
        self.ensure_one()
        self.interview_passed = True

    def _get_offer_values(self):
        # Reporting To 默认取部门 manager
        vals = super()._get_offer_values()
        if not vals.get("reporting_to_id") and self.department_id.manager_id:
            vals["reporting_to_id"] = self.department_id.manager_id.id
        return vals

    def archive_applicant(self):
        res = super().archive_applicant()
        refused_stage = self.env.ref(
            "tg_hr.hr_recruitment_stage_tg_refused", raise_if_not_found=False
        )
        if refused_stage:
            res.setdefault("context", {})["refused_stage_id"] = refused_stage.id
        return res

    @api.constrains("stage_id")
    def _check_stage_prerequisites(self):
        stage_cache = {}

        def get_stage(xml_id):
            if xml_id not in stage_cache:
                stage_cache[xml_id] = self.env.ref(xml_id, raise_if_not_found=False)
            return stage_cache[xml_id]

        for applicant in self:
            target_index = next(
                (i for i, xid in enumerate(self._STAGE_SEQUENCE)
                 if (s := get_stage(xid)) and s.id == applicant.stage_id.id),
                None,
            )
            if target_index is None:
                continue

            missing = [
                label
                for xid in self._STAGE_SEQUENCE[:target_index + 1]
                for field_name, label in self._STAGE_ENTRY_REQUIREMENTS.get(xid, [])
                if not applicant[field_name]
            ]
            if missing:
                raise ValidationError(
                    _("Cannot move to this stage. Please complete: %s")
                    % ", ".join(missing)
                )

    # ─────────────────────────────────────────────────────────────────────
    # Constrains: Onboarding 字段格式校验
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('ob_identification_id', 'ob_region')
    def _check_nid_format(self):
        for rec in self:
            val = (rec.ob_identification_id or '').strip()
            if not val:
                continue
            if rec.ob_region in _BD_REGIONS:
                if not _BD_NID_RE.match(val):
                    raise ValidationError(_(
                        'NID format invalid. Must be:\n'
                        '• Smart ID: 10 digits\n'
                        '• Analog ID: 17 digits'
                    ))
            elif rec.ob_region == 'cn':
                if not _CN_ID_RE.match(val):
                    raise ValidationError(_(
                        'China ID must be 18 characters.'
                    ))

    @api.constrains('ob_passport_id', 'ob_region')
    def _check_passport_format(self):
        for rec in self:
            val = (rec.ob_passport_id or '').strip()
            if not val or rec.ob_region != 'cn':
                continue
            if not _CN_PASSPORT_RE.match(val):
                raise ValidationError(_(
                    'China passport format invalid. Must be:\n'
                    '• E + 8 digits (e.g. E12345678), or\n'
                    '• E + 1 letter (not I/O) + 7 digits (e.g. EA1234567)'
                ))

    @api.constrains('ob_bank_account_number', 'ob_region')
    def _check_bank_account_format(self):
        for rec in self:
            val = re.sub(r'\s', '', rec.ob_bank_account_number or '')
            if not val:
                continue
            if rec.ob_region in _BD_REGIONS:
                if not _BD_BANK_RE.match(val):
                    raise ValidationError(_(
                        'Bank account number invalid. Accepted lengths:\n'
                        '• 11 digits (DBBL)\n'
                        '• 13 digits (BRAC Bank / Dhaka Bank)\n'
                        '• 17 digits (IBBL)'
                    ))
            elif rec.ob_region == 'cn':
                if not _CN_BANK_RE.match(val):
                    raise ValidationError(_(
                        'China bank account (UnionPay) must be 16–19 digits.'
                    ))

    @api.constrains('partner_phone', 'ob_region')
    def _check_phone_format(self):
        for rec in self:
            val = re.sub(r'[\s\-\(\)]', '', rec.partner_phone or '')
            if not val:
                continue
            if rec.ob_region == 'sg':
                if not _PHONE_8_RE.match(val):
                    raise ValidationError(_('Singapore phone number must be 8 digits (local number).'))
            elif rec.ob_region in (*_BD_REGIONS, 'cn'):
                if not _PHONE_11_RE.match(val):
                    raise ValidationError(_('Phone number must be 11 digits (local number, excluding country code).'))

    @api.constrains("review_date")
    def _check_review_date_not_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.review_date and rec.review_date > today:
                raise ValidationError(_("Review Date cannot be in the future."))

    @api.constrains("first_contact_date")
    def _check_first_contact_date_not_future(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.first_contact_date and rec.first_contact_date > today:
                raise ValidationError(_("First Contact Date cannot be in the future."))

    # ─────────────────────────────────────────────────────────────────────
    # Compute: Onboarding Checklist
    # ─────────────────────────────────────────────────────────────────────

    @api.depends('ob_safety_training_notes')
    def _compute_ob_safety_training_confirmed(self):
        for rec in self:
            rec.ob_safety_training_confirmed = bool(rec.ob_safety_training_notes)

    @api.depends('partner_name', 'ob_sex', 'ob_birthday',
                 'ob_nationality_id', 'partner_phone', 'ob_emergency_contact', 'ob_emergency_phone')
    def _compute_chk_personal_info(self):
        for rec in self:
            rec.chk_personal_info = bool(
                rec.partner_name and rec.ob_sex and
                rec.ob_birthday and rec.ob_nationality_id and rec.partner_phone and
                rec.ob_emergency_contact and rec.ob_emergency_phone
            )

    @api.depends('ob_region', 'ob_identification_id', 'ob_passport_id', 'ob_passport_expiration_date')
    def _compute_chk_id_info(self):
        for rec in self:
            region = rec.ob_region
            if region in ('tb', 'tl'):
                rec.chk_id_info = bool(rec.ob_identification_id)
            elif region in ('sg', 'cn'):
                nid_ok = bool(rec.ob_identification_id)
                pp_ok = bool(rec.ob_passport_id) and bool(rec.ob_passport_expiration_date)
                rec.chk_id_info = nid_ok or pp_ok
            else:
                rec.chk_id_info = False

    @api.depends('ob_region', 'onboarding_attachment_ids', 'onboarding_attachment_ids.attachment_type')
    def _compute_chk_id_documents(self):
        for rec in self:
            region = rec.ob_region
            attachments = rec.onboarding_attachment_ids
            if region in ('tb', 'tl'):
                rec.chk_id_documents = any(a.attachment_type == 'nid' for a in attachments)
            elif region in ('sg', 'cn'):
                rec.chk_id_documents = any(a.attachment_type in ('nid', 'passport') for a in attachments)
            else:
                rec.chk_id_documents = False

    @api.depends('ob_bank_name', 'ob_bank_account_number', 'ob_bank_account_holder')
    def _compute_chk_bank_info(self):
        for rec in self:
            rec.chk_bank_info = bool(rec.ob_bank_name and rec.ob_bank_account_number and rec.ob_bank_account_holder)

    @api.depends('ob_region', 'ob_tin_number')
    def _compute_chk_tax_info(self):
        for rec in self:
            if rec.ob_region in ('tb', 'tl'):
                rec.chk_tax_info = bool(rec.ob_tin_number)
            else:
                rec.chk_tax_info = True

    @api.depends('ob_employee_type', 'job_id', 'department_id', 'ob_manager_id',
                 'salary_proposed', 'ob_trial_period_months')
    def _compute_chk_contract_info(self):
        for rec in self:
            rec.chk_contract_info = bool(
                rec.ob_employee_type and rec.job_id and rec.department_id and
                rec.ob_manager_id and rec.salary_proposed and rec.ob_trial_period_months
            )

    @api.depends('onboarding_attachment_ids', 'onboarding_attachment_ids.attachment_type')
    def _compute_chk_diploma(self):
        for rec in self:
            rec.chk_diploma = any(a.attachment_type == 'diploma' for a in rec.onboarding_attachment_ids)

    @api.depends('onboarding_attachment_ids', 'onboarding_attachment_ids.attachment_type')
    def _compute_chk_resignation_proof(self):
        for rec in self:
            rec.chk_resignation_proof = any(
                a.attachment_type == 'resignation_proof' for a in rec.onboarding_attachment_ids
            )

    @api.depends('ob_position_type', 'ob_visa_no',
                 'ob_visa_expire', 'ob_work_permit_expiration_date')
    def _compute_chk_expat_info(self):
        for rec in self:
            if rec.ob_position_type == 'expat':
                rec.chk_expat_info = bool(
                    rec.ob_visa_no and rec.ob_visa_expire and rec.ob_work_permit_expiration_date
                )
            else:
                rec.chk_expat_info = True

    @api.depends('ob_position_type', 'ob_safety_training_confirmed')
    def _compute_chk_safety_training(self):
        for rec in self:
            if rec.ob_position_type == 'factory':
                rec.chk_safety_training = rec.ob_safety_training_confirmed
            else:
                rec.chk_safety_training = True

    @api.depends(
        'ob_region', 'ob_position_type',
        'chk_personal_info', 'chk_id_info', 'chk_id_documents', 'chk_bank_info', 'chk_tax_info',
        'chk_contract_info', 'chk_diploma', 'chk_resignation_proof',
        'chk_expat_info', 'chk_safety_training',
    )
    def _compute_onboarding_progress(self):
        for rec in self:
            items = list(_ALWAYS_CHK)
            for field_name, cond in _COND_CHK.items():
                if cond(rec):
                    items.append(field_name)
            total = len(items)
            done = sum(1 for f in items if rec[f])
            rec.onboarding_total_count = total
            rec.onboarding_done_count = done
            rec.onboarding_progress = (done / total * 100.0) if total else 100.0
            rec.onboarding_complete = (done == total) if total else True

    # ─────────────────────────────────────────────────────────────────────
    # Talent pool（标准 hr_recruitment）：多条人才主档命中时取最早一条
    # ─────────────────────────────────────────────────────────────────────

    def link_applicant_to_talent(self):
        # @Override
        # 标准实现 search 无 order/limit，同联系方式多条「人才」时会得到多记录集，写入
        # pool_applicant_id 可能异常；这里按最早创建的人才主档（稳定 canonical），且只取一条。
        talent = self.env["hr.applicant"].search(
            domain=self._get_similar_applicants_domain(only_talent=True),
            order="create_date asc, id asc",
            limit=1,
        )
        self.pool_applicant_id = talent

    # ─────────────────────────────────────────────────────────────────────
    # Onboarding Actions
    # ─────────────────────────────────────────────────────────────────────

    def action_open_create_employee_wizard(self):
        self.ensure_one()
        if not self.env.user.has_groups(
            "tg_hr.group_tg_hr_onboarding_create_employee,base.group_system"
        ):
            raise AccessError(
                _("You do not have permission to create an employee from this applicant.")
            )
        return {
            'name': self.env._('Create Employee'),
            'type': 'ir.actions.act_window',
            'res_model': 'tg.hr.applicant.create.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_department_id': self.department_id.id or False,
                'default_manager_id': self.ob_manager_id.id or False,
            },
        }

    @api.onchange("department_id")
    def _onchange_department_id_set_ob_manager(self):
        # form 上选/改部门时，若 ob_manager_id 为空则自动填部门 manager
        if not self.ob_manager_id and self.department_id and self.department_id.manager_id:
            self.ob_manager_id = self.department_id.manager_id

    def create_employee_from_applicant(self):
        self.ensure_one()
        if not self.onboarding_complete:
            raise UserError(_('Please complete all Onboarding Checklist items before creating an employee.'))
        action = super().create_employee_from_applicant()
        employee = self.env['hr.employee'].browse(action.get('res_id'))
        if not employee:
            return action
        self.employee_id = employee.id
        # 回写 employee 到该 applicant 的所有 offer，便于追溯
        offers_to_link = self.salary_offer_ids.filtered(lambda o: not o.employee_id)
        if offers_to_link:
            offers_to_link.sudo().write({'employee_id': employee.id})
        self._load_contract_template_from_offer(employee)
        self._create_employee_bank_account(employee)
        self._push_onboarding_attachments(employee)
        return action

    def _load_contract_template_from_offer(self, employee):
        offer = self._get_latest_approved_offer()
        if not offer:
            _logger.warning('tg_hr: no approved offer found for applicant %s (id=%s)', self.partner_name, self.id)
            return
        template = offer.contract_template_id or offer.employee_version_id
        if not template:
            _logger.warning('tg_hr: offer %s has no contract_template_id or employee_version_id', offer.id)
            return
        # 入职档案组对 hr.version 仅只读：模板取值与回写 version 走 sudo，避免依赖 hr.group_hr_user 写版本
        vals = self.env['hr.version'].sudo().get_values_from_contract_template(template)
        if not vals:
            _logger.warning('tg_hr: get_values_from_contract_template returned empty for template %s', template.id)
            return
        employee.write(vals)
        vers = employee.sudo().version_id
        if vers:
            vers.sudo().write({'contract_template_id': template.id})

    def _create_employee_bank_account(self, employee):
        if not self.ob_bank_account_number:
            return
        bank = False
        bic = (self.ob_swift_code or '').strip().upper()
        if bic:
            bank = self.env['res.bank'].search([('bic', '=', bic)], limit=1)
        if not bank and self.ob_bank_name:
            bank = self.env['res.bank'].search(
                [('name', 'ilike', self.ob_bank_name.strip())], limit=1
            )
        if not bank:
            bank = self.env['res.bank'].create({
                'name': self.ob_bank_name or _('Unknown Bank'),
                'bic': bic or False,
            })
        partner = employee.work_contact_id or employee.address_home_id
        if not partner:
            return

        partner_bank = self.env['res.partner.bank'].search([
            ('partner_id', '=', partner.id),
            ('acc_number', '=', self.ob_bank_account_number.strip()),
        ])
        if not partner_bank:
            partner_bank = self.env['res.partner.bank'].sudo().create({
                'acc_number': self.ob_bank_account_number.strip(),
                'partner_id': partner.id,
            })
        partner_bank.write({
            'acc_holder_name': self.ob_bank_account_holder or False,
            'bank_id': bank.id,
        })
        employee.bank_account_ids = [(4, partner_bank.id)]

    def _get_employee_create_vals(self):
        vals = super()._get_employee_create_vals()
        # 试用期起点优先取 wizard 传入的 join_date（context），fallback 到 today
        join_date = self.env.context.get("tg_hr_create_employee_join_date") or fields.Date.context_today(self)
        trial_end = False
        if self.ob_trial_period_months:
            trial_end = join_date + relativedelta(months=self.ob_trial_period_months)
        vals.update({
            'legal_name': self.local_name or vals.get('legal_name') or self.partner_name or False,
            'private_email': self.email_from or False,
            'private_phone': self.partner_phone or False,
            'identification_id': self.ob_identification_id or False,
            'passport_id': self.ob_passport_id or False,
            'passport_expiration_date': self.ob_passport_expiration_date or False,
            'sex': self.ob_sex or False,
            'birthday': self.ob_birthday or False,
            'country_id': self.ob_nationality_id.id,
            'private_country_id': self.ob_nationality_id.id,
            'emergency_contact': self.ob_emergency_contact or False,
            'emergency_phone': self.ob_emergency_phone or False,
            'employee_type': self.ob_employee_type,
            'parent_id': self.ob_manager_id.id if self.ob_manager_id else False,
            'trial_date_end': trial_end,
            'permit_no': self.ob_visa_no or False,
            'visa_expire': self.ob_visa_expire or False,
            'work_permit_expiration_date': self.ob_work_permit_expiration_date or False,
            'join_date': join_date,
        })
        return vals

    def _push_onboarding_attachments(self, employee):
        IrAttachment = self.env['ir.attachment'].sudo()
        for att in self.onboarding_attachment_ids:
            if not att.file:
                continue
            IrAttachment.create({
                'name': att.file_filename or att.name or 'document',
                'datas': att.file,
                'res_model': 'hr.employee',
                'res_id': employee.id,
                'description': att.attachment_type,
            })
        work_permit_atts = self.onboarding_attachment_ids.filtered(
            lambda a: a.attachment_type == 'work_permit' and a.file
        )
        if work_permit_atts:
            newest = work_permit_atts.sorted('id', reverse=True)[0]
            employee.sudo().has_work_permit = newest.file

    def action_generate_offer(self):
        if self.env.user.has_group('tg_hr.group_hr_offer_email_sender'):  # 有权限的时候做 sudo 提权
            return super(HrApplicant, self.sudo()).action_generate_offer()
    
        return super().action_generate_offer()

    def _check_interviewer_access(self):
        # @OVERRIDE 支持入职管理员操作
        if self.env.user.has_group('hr_recruitment.group_hr_recruitment_interviewer') and not self.env.user.has_group('hr_recruitment.group_hr_recruitment_user') and not self.env.user.has_group('tg_hr.group_tg_hr_applicant_records_admin'):
            raise UserError(_('You are not allowed to perform this action.'))
