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
