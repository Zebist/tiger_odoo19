# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models


class FormReadonlyMixin(models.AbstractModel):
    """通用视图只读 mixin（form + list）。

    机制对齐 OCA `base_tier_validation`：在 `get_view` 里扫 arch，把每个顶层
    `<field>` 的 `readonly` 表达式 OR 上一段子类自定义条件。client 端按记录逐个
    evaluate 该表达式：

      - form 视图：一张表只渲染一条记录 → 表达式命中即整张表 readonly。
      - list 视图：每行独立 evaluate → 命中的行整行 readonly，未命中的行可编。
                  天然 row-level conditional readonly，multi_edit / inline edit
                  在审批中的行都进不了编辑模式。

    嵌入 list 内层（form 里 x2many 子表内）的 `<field>` 不动，靠父 x2many 字段
    被锁带动整块 list 进只读。

    用法：
        class HrPayslip(models.Model):
            _inherit = ['hr.payslip', 'form.readonly.mixin']

            def _get_view_readonly_expr(self):
                return "run_approval_state in ('approving', 'approved')"

            def _get_view_readonly_depends(self):
                # 表达式里引用的字段名；mixin 会自动 ensure 它们出现在 arch 里
                return ('run_approval_state',)
    """
    _name = 'form.readonly.mixin'
    _description = 'Form Readonly Mixin'

    def _get_view_readonly_expr(self):
        """返回一段 view-side 表达式字符串；client 端按记录逐个 evaluate，
        命中（True）时该记录在 form/list 上的字段进入 readonly。
        空串/False 表示不启用。"""
        return ""

    def _get_view_readonly_depends(self):
        """返回 `_get_view_readonly_expr` 表达式里引用的字段名 tuple。
        mixin 会确保这些字段存在于注入后的 arch 中（form 里塞 invisible，
        list 里塞 column_invisible），避免 client 端 'Name X is not defined'。"""
        return ()

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type not in ('form', 'list'):
            return res
        expr = self._get_view_readonly_expr()
        if not expr:
            return res
        doc = etree.XML(res['arch'])
        if view_type == 'form':
            xpath_q = "//field[@name][not(ancestor::field)]"
        else:
            xpath_q = "/list/field[@name]"
        for node in doc.xpath(xpath_q):
            old = node.attrib.get('readonly')
            node.attrib['readonly'] = f"({old}) or ({expr})" if old else expr

        # 注入表达式依赖的字段（如果 arch 里没声明）
        depends = self._get_view_readonly_depends()
        if depends:
            existing = {n.get('name') for n in doc.xpath("//field[@name][not(ancestor::field)]")}
            missing = [f for f in depends if f not in existing]
            if missing:
                if view_type == 'form':
                    parent = doc.xpath("//sheet")
                    parent = parent[0] if parent else doc
                    attrs = {'invisible': '1'}
                else:
                    parent = doc
                    attrs = {'column_invisible': '1'}
                for fname in missing:
                    el = etree.SubElement(parent, 'field', name=fname, **attrs)
                    el.tail = '\n'

        res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
