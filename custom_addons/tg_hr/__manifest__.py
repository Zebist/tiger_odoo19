# -*- coding: utf-8 -*-
{
    'name': 'TG HR',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'HR extensions',
    'author': 'Tiger-Zebin',
    'depends': [
        'hr',
        'hr_recruitment',
        'mail',
        'base_tier_validation',
        'base_tier_validation_server_action',
        'base_tier_validation_extend_by_zb'
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/tg_hr_groups.xml',
        'data/hr_requisition_stage_data.xml',
        'views/hr_requisition_stage_views.xml',
        'views/hr_requisition_views.xml',
        'views/hr_job_views.xml',
        # Tier Validation 配置数据（审批流/动作）
        'data/tier_validation_data.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
