# -*- coding: utf-8 -*-
{
    'name': 'Base Flow',
    'version': '19.0.1.0.0',
    'category': 'Tools',
    'summary': 'Flow base and approval flow configuration',
    'author': 'Tiger-Zebin',
    'depends': ['base'],
    'data': [
        'security/base_flow_security.xml',
        'security/ir.model.access.csv',
        'wizards/approval_reject_wizard_views.xml',
        'views/approval_action_views.xml',
        'views/approval_flow_views.xml',
        'views/approval_runtime_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

