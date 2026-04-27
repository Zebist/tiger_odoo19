# -*- coding: utf-8 -*-
{
    'name': 'TG HR',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'HR extensions',
    'author': 'Tiger-Zebin',
    'depends': [
        'base_by_zb',
        'hr',
        'hr_payroll',
        'hr_recruitment',
        'hr_contract_salary',
        'documents',
        'mail',
        'base_tier_validation',
        'base_tier_validation_server_action',
        'base_tier_validation_extend_by_zb'
    ],
    'data': [
        'security/tg_hr_groups.xml',
        'security/ir.model.access.csv',
        'security/tg_hr_record_rules.xml',
        'data/hr_requisition_stage_data.xml',
        'data/hr_applicant_stage_data.xml',
        'data/cron_offer_t3_warning.xml',
        'views/hr_requisition_stage_views.xml',
        'views/hr_requisition_views.xml',
        'views/hr_job_views.xml',
        'wizards/hr_applicant_review_wizard_views.xml',
        'wizards/hr_applicant_first_contact_wizard_views.xml',
        'wizards/hr_applicant_interview_wizard_views.xml',
        'wizards/hr_applicant_create_employee_wizard_views.xml',
        'views/hr_applicant_views.xml',
        'views/hr_employee_views.xml',
        # Tier Validation 配置数据（审批流/动作）
        'data/tier_validation_data.xml',
        'views/res_users_views.xml',
        'views/menuitems.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tg_hr/static/src/js/hr_applicant_form_page_focus.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
