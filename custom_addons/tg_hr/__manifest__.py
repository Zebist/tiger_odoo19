# -*- coding: utf-8 -*-
{
    'name': 'TG HR',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'HR extensions',
    'author': 'Tiger-Zebin',
    'depends': ['hr', 'hr_recruitment', 'mail', 'base_flow'],
    'data': [
        'security/ir.model.access.csv',
        'data/hr_requisition_stage_data.xml',
        'views/hr_requisition_stage_views.xml',
        'views/hr_requisition_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
