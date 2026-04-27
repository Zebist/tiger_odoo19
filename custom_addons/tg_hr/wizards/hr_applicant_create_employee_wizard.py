# -*- coding: utf-8 -*-
from odoo import fields, models


class HrApplicantCreateEmployeeWizard(models.TransientModel):
    _name = 'tg.hr.applicant.create.employee.wizard'
    _description = 'Create Employee Wizard'

    applicant_id = fields.Many2one('hr.applicant', required=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Department', required=True)
    manager_id = fields.Many2one('hr.employee', string='Reporting Manager', required=True,
                                 options="{'no_quick_create': True}")
    work_location_id = fields.Many2one('hr.work.location', string='Work Location', required=True)
    resource_calendar_id = fields.Many2one('resource.calendar', string='Working Schedule',
                                           required=True, check_company=True)

    def action_create_employee(self):
        self.ensure_one()
        applicant = self.applicant_id
        applicant.write({
            'department_id': self.department_id.id,
            'ob_manager_id': self.manager_id.id,
        })
        action = applicant.create_employee_from_applicant()
        employee = self.env['hr.employee'].browse(action.get('res_id'))
        if employee:
            employee.resource_calendar_id = self.resource_calendar_id.id
            employee.sudo().version_id.work_location_id = self.work_location_id.id
        return action
