# -*- coding: utf-8 -*-
from odoo import fields, models


class TgHrRequisitionStage(models.Model):
    _name = 'tg.hr.requisition.stage'
    _description = 'Job Requisition Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    fold = fields.Boolean(
        string='Folded in Kanban',
        help='This stage is folded in the kanban view when there are no records in that column.',
    )
    code = fields.Char(
        string='Workflow Code',
        required=True,
        copy=False,
        index=True,
        help='Stable technical key for transitions and automation (e.g. draft, submitted, hm_assigned, hired).',
    )

    _sql_constraints = [
        ('tg_hr_requisition_stage_code_unique', 'unique(code)', 'Each workflow code may only have one requisition stage.'),
    ]
