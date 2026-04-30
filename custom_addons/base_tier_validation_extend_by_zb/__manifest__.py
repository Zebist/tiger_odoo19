{
    "name": "Base Tier Validation - Extend (ZB)",
    "summary": "Common extensions for base_tier_validation",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "author": "Tiger-Zebin",
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base_tier_validation",
        "base_tier_validation_server_action",
    ],
    "data": [
        "security/tier_validation_extend_security.xml",
        "security/ir.model.access.csv",
        "views/base_approval_flow_views.xml",
        "views/tier_validation_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "base_tier_validation_extend_by_zb/static/src/tier_review_kanban_widget.esm.js",
            "base_tier_validation_extend_by_zb/static/src/tier_review_template_fix.xml",
        ],
    },
}

