from odoo.tools import config

from . import models

if config.get('test_enable'):
    from . import tests  # noqa: F401
