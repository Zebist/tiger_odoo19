# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.base_flow.models.approval_action import register_approval_action_code  # type: ignore


class TgHrRequisitionHiredPerson(models.Model):
    _name = 'tg.hr.requisition.hired.person'
    _description = 'Job Requisition Hired Person'
    _order = 'sequence, id'

    requisition_id = fields.Many2one(
        'tg.hr.requisition',
        string='Requisition',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10, required=True)
    name = fields.Char(string='Hired Person Name', required=True)
    contact = fields.Char(string='Contact Information')
    joining_date = fields.Date(string='Joining Date')
    cv = fields.Binary(string='Hired person CV')
    cv_filename = fields.Char(string='Hired person CV Filename')


class TgHrRequisition(models.Model):
    _name = 'tg.hr.requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'flow.mixin']
    _description = 'Job Requisition'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True, help='e.g. role or project name for this requisition.', translate=True)
    sequence = fields.Integer(string='Sequence', default=10, required=True)
    active = fields.Boolean(default=True, required=True)
    date_request = fields.Date(string='Date of Request', default=fields.Date.context_today, required=True)
    priority = fields.Selection(
        selection=[
            ('1', 'Low'),
            ('2', 'Moderate'),
            ('3', 'Urgent'),
        ],
        string='Priority',
        default='1',
        required=True,
        help='Same scale as project tasks for the star priority widget.',
    )
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    job_id = fields.Many2one('hr.job', string='Job Position', required=True)
    requester_id = fields.Many2one(
        'res.users', string='Requested By', default=lambda self: self.env.user, required=True,
    )
    reporting_to_id = fields.Many2one('res.users', string='Reporting To', required=True)
    hiring_manager_id = fields.Many2one('res.users', string='Hiring Manager')
    hiring_type = fields.Selection(
        selection=[
            ('replacement', 'Replacement'),
            ('new', 'New Role'),
        ],
        string='Hiring Type',
        required=True,
    )
    replacement_partner_id = fields.Many2one(
        'res.partner',
        string='Replacement',
        help='Required when hiring type is Replacement. Cleared when hiring type is New Role.',
    )
    date_join_expected = fields.Date(string='Expected Date of Joining', required=True)
    reason_requisition = fields.Text(string='Reason for Requisition', required=True, default='')
    number_of_vacancies = fields.Selection(
        selection=[
            ('1', '1'),
            ('2', '2'),
            ('3', '3'),
            ('4', '4'),
            ('4_plus', '4+'),
        ],
        string='Number of Vacancies',
        default='1',
        required=True,
    )
    salary_grade = fields.Char(string='Salary Range / Grade', required=True, default='')
    key_responsibility = fields.Html(string='Key Responsibility', required=True, default='<p></p>')
    key_skills = fields.Text(string='Key Skills / Competencies', required=True, default='')
    experience_years = fields.Char(string='Years of Experience Required', required=True)
    description = fields.Html(string='Internal Notes', required=True, default='<p></p>')
    stage_id = fields.Many2one(
        'tg.hr.requisition.stage',
        string='Stage',
        ondelete='restrict',
        tracking=True,
        required=True,
        copy=False,
        index=True,
        default=lambda self: self._default_stage_id(),
        group_expand='_read_group_stage_id',
    )
    stage_code = fields.Char(
        related='stage_id.code',
        string='Stage Code',
        readonly=True,
    )
    hiring_status = fields.Selection(
        selection=[
            ('not_hired', 'Not Hired'),
            ('hired', 'Hired'),
        ],
        string='Hiring Status',
        default='not_hired',
        required=True,
        tracking=True,
    )
    hired_person_ids = fields.One2many(
        'tg.hr.requisition.hired.person',
        'requisition_id',
        string='Hiring Information Person',
    )

    @api.model
    def _default_stage_id(self):
        draft = self.env.ref('tg_hr.requisition_stage_draft', raise_if_not_found=False)
        if draft:
            return draft.id
        return self.env['tg.hr.requisition.stage'].search([('code', '=', 'draft')], limit=1).id

    @api.model
    def _read_group_stage_id(self, stages, domain):
        """Show every requisition stage as a kanban column, even with zero records."""
        Stage = self.env['tg.hr.requisition.stage']
        return Stage.search([], order=Stage._order)

    @api.constrains('hiring_type', 'replacement_partner_id')
    def _check_replacement_partner(self):
        for rec in self:
            if rec.hiring_type == 'replacement' and not rec.replacement_partner_id:
                raise ValidationError(_('Replacement contact is required when hiring type is Replacement.'))

    @api.onchange('hiring_type')
    def _onchange_hiring_type(self):
        if self.hiring_type != 'replacement':
            self.replacement_partner_id = False

    def write(self, vals):
        if vals.get('hiring_type') and vals['hiring_type'] != 'replacement':
            vals = dict(vals, replacement_partner_id=False)

        return super().write(vals)

    @register_approval_action_code('hr_requisition_assigned', label=_('Hiring Manager Assign'))
    def hr_requisition_assigned(self, document, runtime_line):
        """审批动作：指派 Hiring Manager。

        该方法由 `approval.action` 的 code=``hr_requisition_assigned`` 调用。
        """
        self.ensure_one()
        self.write({'hiring_manager_id': self.env.uid})
        return True

    @register_approval_action_code('ceo_approve_on_job_is_manager', label=_('Hiring Manager Approve'))
    def ceo_approve_on_job_is_manager(self, document, runtime_line):
        """审批动作：当岗位是 manager 级别时，需要CEO 审批。

        该方法由 `approval.action` 的 code=``ceo_approve_on_job_is_manager`` 调用。
        """
        self.ensure_one()
        self.write({'hiring_manager_id': self.env.uid})
        return True
