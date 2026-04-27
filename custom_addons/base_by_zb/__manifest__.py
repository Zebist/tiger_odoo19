# -*- coding: utf-8 -*-
{
    'name': 'Base by ZB',
    'version': '19.0.1.0.0',
    'category': 'Technical',
    'summary': 'Base configurations and utilities',
    'author': 'Tiger-Zebin',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'base_by_zb/static/src/js/required_fields_notification.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
