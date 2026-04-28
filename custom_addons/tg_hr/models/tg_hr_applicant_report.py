# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class TgHrApplicantReport(models.Model):
    _name = "tg.hr.applicant.report"
    _description = "Recruitment Analysis"
    _auto = False
    _order = "create_date desc"

    applicant_id = fields.Many2one("hr.applicant", string="Applicant", readonly=True)
    requisition_id = fields.Many2one("tg.hr.requisition", string="Requisition", readonly=True)
    hiring_manager_id = fields.Many2one("res.users", string="Hiring Manager", readonly=True)
    assigned_hr_id = fields.Many2one("res.users", string="Assigned HR", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    department_id = fields.Many2one("hr.department", string="Department", readonly=True)
    job_id = fields.Many2one("hr.job", string="Job Position", readonly=True)
    stage_id = fields.Many2one("hr.recruitment.stage", string="Current Stage", readonly=True)
    create_date = fields.Datetime(string="Created On", readonly=True)
    active = fields.Boolean(readonly=True)

    # Boolean-as-Integer so pivot can SUM them.
    is_reviewed = fields.Integer(string="Reviewed", readonly=True, aggregator="sum")
    is_entered_interview = fields.Integer(string="Entered Interview", readonly=True, aggregator="sum")
    is_offered = fields.Integer(string="Offered", readonly=True, aggregator="sum")
    is_contract_signed = fields.Integer(string="Contract Signed", readonly=True, aggregator="sum")
    is_refused = fields.Integer(string="Refused", readonly=True, aggregator="sum")

    # Cumulative days spent in each stage across all visits.
    days_in_initial = fields.Float(string="Days in Initial Screening", readonly=True, aggregator="avg")
    days_in_contacted = fields.Float(string="Days in Contacted", readonly=True, aggregator="avg")
    days_in_interview = fields.Float(string="Days in Interview", readonly=True, aggregator="avg")
    days_in_offered = fields.Float(string="Days in Offered", readonly=True, aggregator="avg")

    def _stage_id(self, xmlid):
        rec = self.env.ref(xmlid, raise_if_not_found=False)
        return rec.id if rec else 0

    def init(self):
        # 招聘漏斗分析视图，核心逻辑：
        # 从 mail_tracking_value 还原每个候选人的阶段变更历史，
        # 计算在每个阶段的累计停留天数，并展开为分析宽表。
        #
        # CTE 流水线：
        #
        # 1. stage_field
        #    取 hr.applicant.stage_id 字段的 ir_model_fields.id，
        #    用于过滤 mail_tracking_value 只保留阶段变更记录。
        #
        # 2. tracking
        #    从 mail_tracking_value + mail_message 读取所有候选人的
        #    阶段变更记录（old_stage → new_stage，含时间戳）。
        #    注：JOIN mail_message 用内连接，tracking_value 一定有对应 message。
        #
        # 3. first_tracking
        #    DISTINCT ON 取每人最早一条变更的 old_stage，
        #    还原创建时的真实初始阶段（hr_applicant.stage_id 只存当前值，
        #    历史初始值只能从第一次变更的 old_value 反推）。
        #
        # 4. events
        #    合并两类事件为完整时间线：
        #    - 创建事件（t=create_date，stage=initial_stage，mid=0 排在最前）
        #      COALESCE(ft.initial_stage, a.stage_id)：从未移动过的候选人
        #      first_tracking 里没有记录，fallback 到当前 stage_id。
        #      LEFT JOIN first_tracking 保留从未移动过阶段的候选人。
        #    - 变更事件（t=变更时间，stage=new_stage）
        #
        # 5. segments
        #    LEAD(at) 窗口函数，为每个事件计算"下一个事件的时间"作为离开时间。
        #    最后一段 exited=NULL，表示候选人至今仍在该阶段。
        #
        # 6. seg_days
        #    将每段区间转为天数（秒数/86400），
        #    exited 为 NULL 时用 NOW() 持续计时。
        #
        # 7. stage_totals
        #    按 (applicant_id, stage_id) 聚合，累加多次进出同一阶段的天数。
        #
        # 8. pivoted
        #    行转列：
        #    - SUM(CASE ...)   各阶段累计停留天数
        #    - BOOL_OR(...)    是否曾经进入过某阶段（转化漏斗标记）
        #
        # 最终 SELECT
        #    关联 hr_applicant 维度字段（部门/岗位/HR/公司）和
        #    tg_hr_requisition（获取 hiring_manager_id）。
        #    全部用 LEFT JOIN，保留：
        #    - 没有招聘需求的候选人（requisition_id 为空）
        #    - 从未移动过阶段的候选人（pivoted 里没有记录）
        tools.drop_view_if_exists(self.env.cr, self._table)

        initial = self._stage_id("tg_hr.hr_recruitment_stage_tg_initital")
        contacted = self._stage_id("tg_hr.hr_recruitment_stage_tg_contacted")
        interview = self._stage_id("tg_hr.hr_recruitment_stage_tg_interview")
        offered = self._stage_id("tg_hr.hr_recruitment_stage_tg_offered")
        contract_signed = self._stage_id("hr_recruitment.stage_job5")
        refused = self._stage_id("tg_hr.hr_recruitment_stage_tg_refused")

        sql = f"""
        CREATE OR REPLACE VIEW {self._table} AS (
          WITH stage_field AS (
            SELECT id FROM ir_model_fields
            WHERE model = 'hr.applicant' AND name = 'stage_id'
            LIMIT 1
          ),
          tracking AS (
            SELECT m.res_id        AS applicant_id,
                   m.date          AS at,
                   m.id            AS mid,
                   tv.old_value_integer AS old_stage,
                   tv.new_value_integer AS new_stage
            FROM mail_tracking_value tv
            JOIN mail_message m ON m.id = tv.mail_message_id
            WHERE tv.field_id = (SELECT id FROM stage_field)
              AND m.model = 'hr.applicant'
          ),
          first_tracking AS (
            SELECT DISTINCT ON (applicant_id)
                   applicant_id, old_stage AS initial_stage
            FROM tracking
            ORDER BY applicant_id, at, mid
          ),
          events AS (
            -- synthetic event for stage at applicant creation
            SELECT a.id AS applicant_id,
                   a.create_date AS at,
                   0 AS mid,
                   COALESCE(ft.initial_stage, a.stage_id) AS stage_id
            FROM hr_applicant a
            LEFT JOIN first_tracking ft ON ft.applicant_id = a.id
            UNION ALL
            SELECT applicant_id, at, mid, new_stage AS stage_id
            FROM tracking
          ),
          segments AS (
            SELECT applicant_id, stage_id, at AS entered,
                   LEAD(at) OVER (PARTITION BY applicant_id ORDER BY at, mid) AS exited
            FROM events
          ),
          seg_days AS (
            SELECT applicant_id, stage_id,
                   EXTRACT(EPOCH FROM (COALESCE(exited, NOW() AT TIME ZONE 'UTC') - entered)) / 86400.0 AS days
            FROM segments
            WHERE stage_id IS NOT NULL
          ),
          stage_totals AS (
            SELECT applicant_id, stage_id, SUM(days) AS days
            FROM seg_days
            GROUP BY applicant_id, stage_id
          ),
          pivoted AS (
            SELECT applicant_id,
              SUM(CASE WHEN stage_id = {initial}   THEN days END) AS days_in_initial,
              SUM(CASE WHEN stage_id = {contacted} THEN days END) AS days_in_contacted,
              SUM(CASE WHEN stage_id = {interview} THEN days END) AS days_in_interview,
              SUM(CASE WHEN stage_id = {offered}   THEN days END) AS days_in_offered,
              BOOL_OR(stage_id = {interview})       AS ever_interview,
              BOOL_OR(stage_id = {offered})         AS ever_offered,
              BOOL_OR(stage_id = {contract_signed}) AS ever_contract_signed,
              BOOL_OR(stage_id = {refused})         AS ever_refused
            FROM stage_totals
            GROUP BY applicant_id
          )
          SELECT
            a.id AS id,
            a.id AS applicant_id,
            a.requisition_id,
            r.hiring_manager_id,
            a.assigned_hr_id,
            a.company_id,
            a.department_id,
            a.job_id,
            a.stage_id,
            a.create_date,
            a.active,
            CASE WHEN a.resume_reviewed THEN 1 ELSE 0 END AS is_reviewed,
            CASE WHEN COALESCE(p.ever_interview, FALSE)       THEN 1 ELSE 0 END AS is_entered_interview,
            CASE WHEN COALESCE(p.ever_offered, FALSE)         THEN 1 ELSE 0 END AS is_offered,
            CASE WHEN COALESCE(p.ever_contract_signed, FALSE) THEN 1 ELSE 0 END AS is_contract_signed,
            CASE WHEN COALESCE(p.ever_refused, FALSE)         THEN 1 ELSE 0 END AS is_refused,
            p.days_in_initial,
            p.days_in_contacted,
            p.days_in_interview,
            p.days_in_offered
          FROM hr_applicant a
          LEFT JOIN tg_hr_requisition r ON r.id = a.requisition_id
          LEFT JOIN pivoted p ON p.applicant_id = a.id
        )
        """
        self.env.cr.execute(sql)
