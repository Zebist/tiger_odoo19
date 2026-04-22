# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import safe_eval

# 由装饰器在 import 时写入。
# 同一个 code 重复注册时：后加载的模块覆盖先加载的（与 Odoo 模块加载顺序一致）。
_approval_action_handler_map = {}


def register_approval_action_code(code, label=None):
    """注册 action code 对应的处理方法。

    统一用法：直接使用本模块函数（含扩展模块）。

    - 用法：``@register_approval_action_code('xxx', label=_('...'))``
    """
    def decorator(method):
        label_ = label if label is not None else code
        _approval_action_handler_map[code] = (label_, method.__name__)
        return method
    return decorator


class ApprovalAction(models.Model):
    _name = 'approval.action'
    _description = 'Approval Action'
    _order = 'sequence, name, id'

    active = fields.Boolean(default=True, required=True)
    sequence = fields.Integer(default=10, index=True)
    name = fields.Char(required=True, translate=True)

    # Exactly one of these should be set.
    code = fields.Char(string='Code', index=True)
    python_code = fields.Text(string='Python Code')

    @api.constrains('code', 'python_code')
    def _check_code_python_exclusive(self):
        for rec in self:
            has_code = bool((rec.code or '').strip())
            has_py = bool((rec.python_code or '').strip())
            if has_code == has_py:
                raise ValidationError(_('Please set either Code or Python Code (exactly one).'))

    @api.model
    def _get_code_map(self):
        """Return mapping: code -> (label, method_name).

        由装饰器 :func:`register_approval_action_code` 在 import 时写入
        :data:`_approval_action_handler_map`。

        Other modules may still extend via ``super()._get_code_map()`` and merge keys.
        """
        return dict(_approval_action_handler_map)

    def _run_by_code(self, document, runtime_line=None):
        self.ensure_one()
        code = (self.code or '').strip()
        if not code:
            return

        code_map = self._get_code_map() or {}
        if code not in code_map:
            raise UserError(_('Unknown action code: %(code)s') % {'code': code})

        _label, method_name = code_map[code]
        method = getattr(self, method_name, None)
        if not method:
            raise UserError(_('Action method not found: %(method)s') % {'method': method_name})
        return method(document=document, runtime_line=runtime_line)

    def _run_by_python(self, document, runtime_line=None):
        self.ensure_one()
        python_code = (self.python_code or '').strip()
        if not python_code:
            return

        # Keep execution context explicit; safe_eval prevents unsafe bytecode ops.
        localdict = {
            'env': self.env,
            'user': self.env.user,
            'document': document,
            'runtime_line': runtime_line,
            'action': self,
            '_': _,
        }
        safe_eval(python_code, localdict, mode='exec')

    def run(self, document, runtime_line=None):
        self.ensure_one()
        if (self.code or '').strip():
            return self._run_by_code(document=document, runtime_line=runtime_line)
        return self._run_by_python(document=document, runtime_line=runtime_line)
