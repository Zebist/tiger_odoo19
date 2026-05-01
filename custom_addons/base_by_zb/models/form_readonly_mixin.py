# -*- coding: utf-8 -*-
from lxml import etree

from odoo import api, models


class FormReadonlyMixin(models.AbstractModel):
    """通用视图只读 mixin（form + list + kanban）。

    机制对齐 OCA `base_tier_validation`：在 `get_view` 里扫 arch，把每个顶层
    `<field>` 的 `readonly` 表达式 OR 上一段子类自定义条件。client 端按记录逐个
    evaluate 该表达式：

      - form 视图：一张表只渲染一条记录 → 表达式命中即整张表 readonly。
      - list 视图：每行独立 evaluate → 命中的行整行 readonly，未命中的行可编。
                  天然 row-level conditional readonly，multi_edit / inline edit
                  在审批中的行都进不了编辑模式。
      - kanban 视图：record 卡片内的字段（含 inline edit / quick create 弹层
                    内的字段）按记录 evaluate 命中后只读。

    嵌入 list 内层（form 里 x2many 子表内）的 `<field>` 不动，靠父 x2many 字段
    被锁带动整块 list 进只读。

    白名单：`_get_view_readonly_skip_containers` 返回一组容器 `name`（page / group /
    div / notebook 任意容器都行），命中的容器内所有字段不会被注入 readonly。
    适用于"主要字段都锁住，但某个分页 / 分组里的字段始终允许编辑"的场景。

    用法：
        class HrPayslip(models.Model):
            _inherit = ['hr.payslip', 'form.readonly.mixin']

            def _get_view_readonly_expr(self):
                return "run_approval_state in ('approving', 'approved')"

            def _get_view_readonly_depends(self):
                # 表达式里引用的字段名；mixin 会自动 ensure 它们出现在 arch 里
                return ('run_approval_state',)

            def _get_view_readonly_skip_containers(self):
                # 这些 name 的容器内字段不会被注入 readonly
                return ('manual_adjust_section',)
    """
    _name = 'form.readonly.mixin'
    _description = 'Form Readonly Mixin'

    def _get_view_readonly_expr(self):
        """返回一段 view-side 表达式字符串；client 端按记录逐个 evaluate，
        命中（True）时该记录在 form/list/kanban 上的字段进入 readonly。
        空串/False 表示不启用。"""
        return ""

    def _get_view_readonly_depends(self):
        """返回 `_get_view_readonly_expr` 表达式里引用的字段名 tuple。
        mixin 会确保这些字段存在于注入后的 arch 中（form 里塞 invisible，
        list / kanban 里塞 column_invisible / 顶层声明），避免 client 端
        'Name X is not defined'。"""
        return ()

    def _get_view_readonly_skip_containers(self):
        """返回容器 element 的 `name` 属性 tuple；这些容器（page/group/div/notebook
        等）内部的所有字段不会被注入 readonly，可正常编辑。空 tuple 表示无白名单。"""
        return ()

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type not in ('form', 'list', 'kanban'):
            return res
        expr = self._get_view_readonly_expr()
        if not expr:
            return res
        doc = etree.XML(res['arch'])

        # 白名单跳过条件：跳过 ancestor name 命中任意 skip 名字的字段
        skip_names = self._get_view_readonly_skip_containers()
        skip_filter = ""
        if skip_names:
            skip_clause = " or ".join(f"@name='{n}'" for n in skip_names)
            skip_filter = f"[not(ancestor::*[{skip_clause}])]"

        if view_type == 'form':
            xpath_q = f"//field[@name][not(ancestor::field)]{skip_filter}"
        elif view_type == 'list':
            # list 通常顶层 field 一行；不会有嵌套容器（除非 kanban-style group）
            xpath_q = f"/list/field[@name]{skip_filter}"
        else:  # kanban
            # kanban 里 field 可能在顶层声明（不影响 UI）和 templates 里（影响渲染）
            # 注入 readonly 主要影响 templates 中可编辑场景（quick create / inline edit）
            xpath_q = f"//field[@name][not(ancestor::field)]{skip_filter}"

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
                elif view_type == 'list':
                    parent = doc
                    attrs = {'column_invisible': '1'}
                else:  # kanban
                    parent = doc
                    attrs = {}
                for fname in missing:
                    el = etree.SubElement(parent, 'field', name=fname, **attrs)
                    el.tail = '\n'

        res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
