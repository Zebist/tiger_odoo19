{
    "name": "Tier Validation - Stage Update",
    "summary": "Update document stage on tier approval/rejection",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "author": "Tiger-Zebin",
    "license": "LGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "base_tier_validation_extend_by_zb",
        "base_tier_validation_server_action",
    ],
    "data": [
        "views/tier_definition_views.xml",
    ],
}

