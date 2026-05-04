# base_by_zb

Zebin 维护的基础工具模块（与具体客户品牌解耦，可迁移复用）；跨业务通用的 mixin、工具函数、UI 行为放这里。

---

## form.readonly.mixin

按"业务状态"把 form / list / kanban 视图整体置为只读。客户端按记录逐个 evaluate，
不需要后端 ACL，纯视图层控制。

### 适用场景

- 单据进入"已审批 / 已结算 / 已签署"等终态后禁止编辑
- 列表行级条件只读（已签的行只读，未签的行可编）
- kanban 卡片 inline 编辑 / quick create 在终态时不让改字段
- **白名单容器**：主体只读，但某个 page / group 里的字段仍允许编辑（例如"主体已锁，但 onboarding 资料采集页仍开放"）

### 不适用

- 字段级精细只读（请直接在字段定义或视图上写 `readonly=...`）
- 必须在后端阻止写入的场景（视图只读不防 RPC，安全敏感的写入要 override `write`）

---

## 用法

### 1. 模型 inherit

```python
from odoo import models


class HrApplicant(models.Model):
    _inherit = ["hr.applicant", "form.readonly.mixin"]

    def _get_view_readonly_expr(self):
        # 客户端表达式，evaluate True 时整张视图 / 行字段只读
        return "is_contract_signed_stage"

    def _get_view_readonly_depends(self):
        # 表达式里引用的字段名；mixin 自动确保它们出现在 arch 中
        return ("is_contract_signed_stage",)

    def _get_view_readonly_skip_containers(self):
        # 这些 name 的容器（page/group/div/notebook 任意类型）内字段不被锁
        return ("tg_hr_onboarding",)
```

### 2. 表达式约定

`_get_view_readonly_expr` 返回的是 **Odoo 客户端 domain 表达式语法**（与字段 `readonly="..."`、`invisible="..."` 一致），可以引用：

- 当前记录的字段（store 或非 store 都行，**但非 store 字段必须被 `_get_view_readonly_depends` 声明**）
- 字符串 / 数字 / `True` / `False` / 元组等字面量
- `parent.xxx` 引用父记录字段（在 x2many 子表里）

例：
```python
def _get_view_readonly_expr(self):
    return "state in ('done', 'cancel')"

def _get_view_readonly_expr(self):
    return "approval_state == 'approved' and not is_draft"
```

不能用：Python 函数调用、复杂 lambda、`self.env.ref(...)` —— 这些是 Python 代码，不是客户端表达式。要引用具体记录，先在模型上加一个 compute store boolean 字段。

### 3. 引用 xmlid 的常见做法

需要"等于某条数据记录"时，**不要把 id 数字硬编码到表达式里**（不同环境 id 不同）。先在模型上加 compute store 字段：

```python
is_contract_signed_stage = fields.Boolean(
    compute="_compute_is_contract_signed_stage",
    store=True,
)

@api.depends("stage_id")
def _compute_is_contract_signed_stage(self):
    target = self.env.ref("hr_recruitment.stage_job5", raise_if_not_found=False)
    for rec in self:
        rec.is_contract_signed_stage = bool(target) and rec.stage_id == target
```

然后表达式直接引用 `is_contract_signed_stage`。

### 4. skip_containers 容器命名

mixin 按 `<element name="..."/>` 的 name 属性匹配，**与容器类型无关**：

```xml
<page string="Onboarding" name="tg_hr_onboarding">    <!-- ✅ 跳过 -->
<group name="manual_adjust_section">                  <!-- ✅ 跳过 -->
<div name="signature_block">                          <!-- ✅ 跳过 -->
<notebook name="extra_info">                          <!-- ✅ 跳过 -->
```

即"哪个容器需要排除就给它起 name + 加进 skip 列表"，比指定类型（仅 page 或仅 group）更灵活。

---

## 工作机制

`get_view` 内部：

1. 调用 super 拿到 arch
2. 如果 view_type 不是 form / list / kanban，跳过
3. `_get_view_readonly_expr` 空串则跳过
4. xpath 扫所有顶层 `<field>`（不在 x2many 子 list 内）
5. 排除 `_get_view_readonly_skip_containers` 列出的容器内字段
6. 给每个匹配的 field 把现有 `readonly` 用 `( old ) or ( expr )` 包裹
7. 把 `_get_view_readonly_depends` 列的字段塞进 arch（form 用 `invisible="1"`，list 用 `column_invisible="1"`，kanban 顶层声明），确保客户端 evaluate 时字段已加载

---

## 常见踩坑

| 现象 | 原因 / 修法 |
|---|---|
| 字段没变只读 | 字段在 x2many 子 list 里。锁 x2many 父字段（mixin 会自动给父字段加 readonly）整块表自动只读 |
| `'Name xxx is not defined'` | 表达式引用的字段没声明在 `_get_view_readonly_depends` |
| skip 容器内字段还是只读 | 容器没设 `name` 属性。给容器加 `name="..."` 再加进 skip list |
| kanban 拖拽 stage 还能改 | mixin 不锁拖拽。要锁 stage 字段本身或在后端 `write` 拦截 |
| RPC 直调还能写 | 视图只锁 UI，不防 RPC。安全场景要 override `write` 在后端拦 |

---

## tools.amount

通用工具方法集。

### `amount_to_chinese_upper(amount)`

人民币金额转中文大写（元/角/分），用于合同 / offer 文档预填，非会计核算。

```python
from odoo.addons.base_by_zb.tools.amount import amount_to_chinese_upper

amount_to_chinese_upper(1234.56)
# → "壹仟贰佰叁拾肆元伍角陆分"

amount_to_chinese_upper(0)
# → "零元整"

amount_to_chinese_upper(-100.00)
# → "负壹佰元整"
```
