# -*- coding: utf-8 -*-
{
    'name': 'TG Payroll',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Payroll extensions: structure-type config, contract allowances, payslip KPI grade',
    'author': 'Tiger-Zebin',
    'depends': [
        'hr_payroll',
    ],
    'data': [
        'data/hr_payslip_input_type_data.xml',
        'views/hr_payroll_structure_type_views.xml',
        'views/hr_payslip_input_type_views.xml',
        'views/hr_version_views.xml',
        'views/hr_payslip_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
