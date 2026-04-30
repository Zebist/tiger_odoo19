# -*- coding: utf-8 -*-
{
    'name': 'TG Payroll',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Payroll extensions: structure-type config, contract allowances, payslip KPI grade',
    'author': 'Tiger-Zebin',
    'depends': [
        'hr_payroll',
        'base_by_zb',
        'base_tier_validation_extend_by_zb',
    ],
    'data': [
        'data/hr_payslip_input_type_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/tier_validation_data.xml',
        'views/hr_payroll_structure_type_views.xml',
        'views/hr_payslip_input_type_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_version_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_payslip_run_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'tg_payroll/static/src/scss/payrun_kanban.scss',
            'tg_payroll/static/src/views/payrun_card_extend.xml',
            'tg_payroll/static/src/views/payrun_kanban_record_patch.esm.js',
            'tg_payroll/static/src/views/payslip_list_controller_patch.esm.js',
            'tg_payroll/static/src/components/payslip_action_helper_patch.esm.js',
            'tg_payroll/static/src/components/payslip_action_helper_patch.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
