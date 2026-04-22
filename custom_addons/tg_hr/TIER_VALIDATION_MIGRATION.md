# tg_hr：从 base_flow 迁移到 OCA Tier Validation（方案草案）

## 背景与目标
当前 `tg_hr` 的 `tg.hr.requisition` 使用自研模块 `base_flow`（`flow.mixin`）实现审批：
- 配置：`approval.flow` / `approval.node`
- 运行：`approval.runtime` / `approval.runtime.line`
- UI：表单按钮 `Submit/Approve/Reject` + Approval Info 区块
- 动作：审批通过时执行 `approval.action`（例如自动 assign）

目标是改为使用 OCA 的 Tier Validation 体系：
- **可配置审批流**：`tier.definition`
- **页面展示审批**：OCA 内置 widget/按钮/审批历史
- **审批通过/驳回执行动作**：通过 `ir.actions.server`（服务器动作）
- **CEO 是否需要审批**：先用 `definition_domain`（你已确认）

> 说明：你要求“适配模块不用新建，直接改 `tg_hr`”。本方案按此执行（后续进入开发会直接改 `custom_addons/tg_hr`）。


## 需要启用的模块（本仓库已有代码）
- 必装（核心）
  - `base_tier_validation`
  - `base_tier_validation_server_action`（审批通过/驳回触发 server action，用于 auto-assign、推进 stage 等）
- 建议暂不装（本轮先不用）
  - `base_tier_validation_formula`（你先用 `definition_domain` 试试）
  - `base_tier_validation_forward`（转交/加签）


## 迁移后核心概念映射
### 审批状态怎么表达
OCA 不推荐用你现在的 `state = draft/approving/approved` 来当“审批状态”。
- **审批状态字段**：`validation_status`（`no/waiting/pending/rejected/validated`）
- **每一级审批状态**：`tier.review.status`（`waiting/pending/approved/rejected`）

业务本身的流程（例如招聘申请“草稿/已提交/已指派/已完成”）仍然应由你的业务字段（现在是 `stage_id(code)`）来表达。


## 关键问题：什么是“审批拦截点”？你需要做什么？
### 1) OCA 是怎么“卡住”业务动作的
`tier.validation` 的机制是：当业务单据写入某个“业务状态字段”从 **from → to** 的那一刻，它会判断是否需要审批：
- 需要审批：会要求先 `request_validation`，否则抛错阻止进入目标状态
- 不需要审批：允许直接进入目标状态

### 2) 为什么我一直问“拦截点放在哪个迁移上”
因为你现在的 `tg.hr.requisition` 主要靠 `stage_id` 在流转，但 OCA 默认拦截的是一个 **可枚举的业务状态字段**（默认叫 `state`）。
迁移后我们必须明确：**哪一步算“要被审批卡住的关键动作”**。

### 3) 你要做的事情（只需要选业务规则）
你只需要回答一句话：**“招聘申请在哪一步必须经过审批，才能继续？”** 例如二选一（常见做法）：
- 选项 A：`draft -> submitted` 必须审批
  - 含义：一点击提交就开始走审批；没批完不能进入“已提交/流转中”的阶段
- 选项 B：`submitted -> hm_assigned` 必须审批
  - 含义：允许先提交进入队列，但真正“指派 Hiring Manager/推进到 hm_assigned 阶段”这一步要审批通过才行

你不用写代码；只要确定业务想要的体验与管控点即可。我们会据此在开发时配置 `tier.validation` 的 `_state_from/_state_to`（或等价的业务拦截点实现）。

> 推荐：如果你希望“提交就必须受控”，选 A；如果你希望“先提交排队，关键动作再受控”，选 B。


## 具体改动清单（进入开发阶段会做）
### 1) tg_hr 依赖切换
修改 `custom_addons/tg_hr/__manifest__.py`：
- 移除依赖：`base_flow`
- 增加依赖：`base_tier_validation`、`base_tier_validation_server_action`

### 2) 模型层：`tg.hr.requisition` 接入 Tier Validation
修改 `custom_addons/tg_hr/models/hr_requisition.py`：
- `_inherit`：移除 `flow.mixin`，改为继承 `tier.validation`
- 移除/替换旧审批动作：
  - `action_submit/action_approve/action_open_reject_wizard/...`（来自 `flow.mixin`）
  - `register_approval_action_code(...)`（旧的 base_flow action 机制）
- 配置 OCA 注入 UI（推荐）：
  - 在该模型上设置 `_tier_validation_manual_config = False`，让 OCA 自动注入按钮/审批区块

### 3) 视图层：移除旧审批 UI，采用 OCA UI
修改 `custom_addons/tg_hr/views/hr_requisition_views.xml`：
- 删除旧按钮：`Submit/Approve/Reject/Acknowledge Reason`（它们调用的是 `flow.mixin` 方法）
- 删除旧审批展示区块：`state/is_current_approver/approval_runtime_id/approve_note`
- 保留你的业务字段区块、`stage_id` statusbar、看板等

### 4) 配置：Tier Definition（审批流）+ Server Action（动作）
在 `tg_hr` 中新增数据 XML（开发阶段做）：
- `tier.definition`：
  - 第 1 层：Hiring Manager（审批人来源可先用“字段/个人/组”）
  - 第 2 层：HR
  - 第 3 层：CEO（`definition_domain`：按 `job_id` 条件生效）
- `ir.actions.server`：
  - auto-assign：审批通过后写 `hiring_manager_id`
  - （可选）推进 `stage_id`：在某一级审批通过后写 `stage_id`（实现你原 `base_flow` 的“节点→阶段”感觉）


## CEO 条件（你已选择 definition_domain）
做法：给 CEO 那一层 `tier.definition` 配 `definition_domain`，只有满足条件的 requisition 才生成 CEO 的 `tier.review`。
示例思路（最终字段名以你 `hr.job` 上实际可用字段为准）：
- 若你用岗位名称/标签：`[('job_id.name', 'ilike', 'Manager')]`
- 若你们有自定义字段：`[('job_id.is_manager', '=', True)]`


## 验收标准（开发完成后你怎么验）
- 业务表单能看到 OCA 的审批区块与按钮（Request/Validate/Reject/Restart）
- “需要审批”的单据：未完成审批前无法越过你选定的拦截点
- 审批通过后：自动执行动作（例如写入 `hiring_manager_id`）
- CEO 条件生效：满足 domain 的单据会多一层 CEO 审批，不满足的不会生成 CEO 审批

