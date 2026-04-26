# Tiger-Zebin Odoo 19 Project Rules

## 作者标识
- `__manifest__.py` 的 `author` 字段统一为 `'Tiger-Zebin'`（连字符，无空格）

## 版本号
- `version` 必须以 `19.0.` 开头，例如 `19.0.1.0.0`
- 不要为记录小改动自行递增 version，仅在用户明确要求时才改

## 代码注释
- 默认使用中文（简体），除非用户明确要求英文

## UI 标签
- `string=` / `help=` 等面向用户的文案使用英文源文本，并保留可翻译性（`_()`）

## x2many 快速创建
- form 视图中的 many2one / many2many 字段默认加 `options="{'no_quick_create': True}"`
- 仅当用户明确要求打开某字段的快速创建时才去掉

## 安全组
- 不在 `res.groups` 上使用 `category_id`，改用 `privilege_id` 体系
- 结构：`ir.module.category` → `res.groups.privilege`（带 category_id）→ `res.groups`（带 privilege_id）
- 按钮/动作需权限时：UI 加 `groups="...,base.group_system"`，后端也做 `has_group(...)` 双重校验
- TransientModel 的 ACL 用 `base.group_user`，不默认加 `base.group_system`

## OCA 优先原则
- 顺序：Odoo 原生能力 → OCA（本地缓存）→ 自研
- 默认只用本地缓存 `.cursor/oca-cache/`，不联网
- 用户明确要求"更新 OCA 数据"时才运行 oca-sync

## Odoo 19 升级踩坑
- `res.groups.users` → `res.groups.user_ids`
- `res.users.groups_id` → `res.users.group_ids`
- `res.groups.category_id` → `privilege_id.category_id`
- `odoo.models.NewId` → `from odoo.api import NewId`
- search view 老写法 `<group expand="0" string="...">` 在 19+ 可能报错，改用不带属性的 `<group>`

## Python/Odoo 19 编码规范
- 不用 `@api.multi` / `@api.one` 等废弃装饰器
- override `create` 用 `@api.model_create_multi`，接收 `vals_list`
- x2many 操作用 `from odoo import Command`（`Command.create/set/link/unlink/clear`）
- ACL 中 `base.group_system` 必须有完整权限（TransientModel 除外）

---

## Skills

### oca-module-finder
触发时机：用户讨论新功能方案、问"有没有 OCA 模块做 X"、或需要避免重复造轮子时。

执行步骤：
1. 从对话中提取业务关键词（如 approval / workflow / hr / stock）
2. 运行本地检索脚本：
   ```bash
   python3 .cursor/skills/oca-module-finder/scripts/search_oca_cache.py "关键词"
   ```
3. 输出：候选模块列表 + 匹配原因 + 采用/替代建议 + 风险点（版本/许可证/改造成本）
4. 若本地缓存命中不足，提示用户是否允许联网更新（运行 oca-sync）

### oca-sync
触发时机：用户明确说"更新 OCA 数据"/"刷新 OCA 缓存"时才运行，默认不联网。

执行步骤：
```bash
python3 .cursor/skills/oca-sync/scripts/sync_oca_sources.py
```
结果写入：
- `.cursor/oca-cache/raw/`（原始 HTML）
- `.cursor/oca-cache/index/`（解析后的 JSON 索引）
