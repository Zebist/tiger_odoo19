# tg_payroll —— 交接文档（给下一个 agent session 看）

> 本文件用于把当前对话上下文传给后续 session。读完应当能直接续做 Phase 2（录入 9 套薪资结构 / 规则）。

## 1. 项目背景

- 项目：Tiger-Zebin Odoo 19 企业版（`/Users/zebin/work/tiger/odoo-19.0+e.20250917/`）
- 自定义 addons 路径：`custom_addons/`，已有 `tg_hr`（招聘/员工扩展）。本次新建 `tg_payroll`（薪资扩展）。
- 用户偏好：见 `~/.claude/projects/-Users-zebin-work-tiger-odoo-19-0-e-20250917/memory/`。重点：作者 `Tiger-Zebin`、`version` 以 `19.0.` 开头、注释中文、UI 文案英文带 `_()`、安全组用 `privilege_id` 体系。
- **Odoo 19 关键差异**：合同模型从 `hr.contract` 改为 `hr.version`（versioned contract）。`wage` / `structure_type_id` / `resource_calendar_id` / `currency_id` 等字段都在 `hr.version` 上；`hr.payslip` 关联合同的字段是 `version_id`（不是 `contract_id`）。

## 2. 整体业务需求（用户原始描述简化版）

跨国家薪资管理：孟加拉（BD）/ 中国（CN）/ 新加坡（SG）三个独立法人。计划做 9 套薪资结构：

| 结构 | 说明 |
|---|---|
| BD_HQ | 孟加拉本地职能 |
| BD_FAC.MGMT | 工厂管理层/职能 |
| BD_SALES_FT | 销售全职 |
| BD_SALES_CT | 销售外包（日薪） |
| BD_WORKER | 工人（含全勤奖 500） |
| BD_IN | 各部门实习生（日薪） |
| CN_FT | 中国正式 |
| CN_CT | 中国外包（日薪） |
| SG_MGMT | 新加坡管理层 |

**用户决定 Phase 1 不预置任何 structure / rule，先搭基础设施**。Phase 2 由用户拿老系统 (从前的旧 Odoo 实现) 一套套发过来，逐套讨论后录入。

### 2.1 BD 三大项拆分

BD 系列合同的 `wage` 拆成 4 项：
- `BASIC` = 50%
- `HRA` (House Rent Allowance) = 25%
- `MEDICAL` = 15%
- `CONVEYANCE` = 10%

合计 100%。**TOTAL 必须严格等于 WAGE**（小数偏差落在 BASIC）。
比例可配置（挂在 `hr.payroll.structure.type` 上）；CN/SG 不拆，比例字段留空，BASIC 直接等于 wage。

### 2.2 INPUT 体系

不在 Odoo 管考勤，每月通过导入 PAYSLIPS + INPUTS 算薪。预置 7 个 input type：

| code | 单位 | 说明 |
|---|---|---|
| ABS | 天 | 缺席天数 |
| LATE | 小时 | 迟到小时 |
| OT | 小时 | 加班小时 |
| KPIBONUS | 金额 | KPI 奖金 |
| ADJ | 金额 | 调整金额（提成、AIT、夜班费、产量奖临时塞这里） |
| EXPAT | 天 | 外派津贴天数 |
| TRIP | 天 | 出差补助天数 |

`ABS/LATE/OT/EXPAT/TRIP` 同时勾 `is_quantity=True`（Odoo 原生），让系统当数量处理。
新增 `unit` 字段（amount/day/hour/percent）只用于展示，不参与计算。

### 2.3 出勤天数 / 日薪

- 出勤天数 = `working_days_per_month - ABS`（默认 26，可按 struct type 配）
- 日薪 = base / `working_days_per_month`，base 由 struct type 的 `absence_base` 决定（`wage` 或 `basic`）
- 用户确认：**缺勤按 wage/26**（即 `absence_base = wage`）
- 合同上不录日薪，全部录 wage（月薪），日薪是 compute 字段（不存储）展示用

### 2.4 迟到扣款算法（已确认）

**所有结构统一使用动态费率**（对齐老系统 Full Time Employment CSV）：

```
per_minute_rate = contract.wage / (working_days_per_month × hours_per_day × 60)
late_deduction  = -(LATE_hours × 60) × per_minute_rate
```

- `working_days_per_month` 取 struct type 配置（默认 26）
- `hours_per_day` 取合同 `resource_calendar_id.hours_per_day`（Odoo 原生，默认 8）
- struct type 上的 `late_rate_mode / late_fixed_per_minute` 字段已建，仍保留以备特殊情况，但目前所有结构录为 `wage_based`

### 2.5 加班费（已确认）

**在合同上加 `overtime` 字段（Monetary，关联 currency_id）**，与老系统 `x_studio_overtime` 对应。
规则公式：`OT_hours × contract.overtime`（overtime 就是每小时加班费，直接配置在合同，不用公式推算）。

> **需要在 hr.version 新增字段**（Phase 1 代码还没加，Phase 2 开始前先补）：
> ```python
> overtime = fields.Monetary(
>     string="Overtime Rate / Hour",
>     currency_field='currency_id',
>     groups="hr_payroll.group_hr_payroll_user",
>     help="Hourly overtime rate paid directly from this field. Rule: OT_hours × overtime.",
> )
> ```
> 并在合同视图 `hr_version_views.xml` 的 Standard Allowances 组里加上此字段。

### 2.6 KPI grade（CN_FT 用，但设计为通用）

PaySlip 上加 `kpi_grade` Selection（A=100% / B=50% / C=0%）。基数从 `hr.version.kpi_base` 取。
- 选了 grade → 自动计算金额，写入 KPIBONUS input
- 没选 grade → 走原本的导入/手填 KPIBONUS
- **校验**：grade 已选时禁止任何方式（手填/导入）写入 KPIBONUS，避免冲突；要先清 grade

### 2.7 标准津贴 vs 明细行（讨论结果）

用户问"每加一个津贴在合同上加字段，还是用 allowance 明细行？"
讨论后决定：
- **本次只做固定字段**（5 个：phone / perfect_attend / expat_daily / trip_daily / housing），规则代码稳定引用
- 不加 `allowance_ids` 长尾明细行（暂时没具体用例）。后续如果出现非标津贴需求，再加

### 2.8 ESOP

用户决定**忽略**，不做。

### 2.9 AIT（孟加拉个税）

Phase 1 暂时丢 ADJ。**Phase 2 强烈建议做成阶梯税表独立规则**（按月累计应税额查税阶），不要长期靠 ADJ。

### 2.10 配置：结构类型 vs 配置表 vs 合同

讨论后决定：**所有薪资政策参数挂在 `hr.payroll.structure.type`**，不单独建配置表，也不放合同。理由：政策同类合同共享，挂结构类型最自然。

## 3. 模块结构

```
custom_addons/tg_payroll/
├── __manifest__.py             # depends: ['hr_payroll']
├── __init__.py
├── HANDOFF.md                  # 本文件
├── models/
│   ├── __init__.py
│   ├── hr_payroll_structure_type.py
│   ├── hr_version.py
│   ├── hr_payslip_input_type.py
│   └── hr_payslip.py
├── data/
│   └── hr_payslip_input_type_data.xml
└── views/
    ├── hr_payroll_structure_type_views.xml
    ├── hr_payslip_input_type_views.xml
    ├── hr_version_views.xml
    └── hr_payslip_views.xml
```

## 4. 模型扩展明细

### `hr.payroll.structure.type` (inherit)

| 字段 | 类型 | 用途 |
|---|---|---|
| `working_days_per_month` | Float, default 26 | 月度工作天数（日薪/缺勤/加班基数） |
| `hra_pct` / `medical_pct` / `conveyance_pct` | Float (0~1) | 三大项占 wage 比例。全 0 = 不拆分 |
| `ot_rate` | Float, default 2.0 | 加班倍率 |
| `absence_base` | Selection wage/basic, default wage | 日薪基数 |
| `late_rate_mode` | Selection wage_based/fixed | 迟到费率模式 |
| `late_fixed_per_minute` | Float | 固定模式下的每分钟费率 |

约束：三大项比例都在 0~1 之间，且总和不能 > 1。

### `hr.version` (inherit, ie 合同)

标准津贴字段（全部 Monetary，groups=`hr_payroll.group_hr_payroll_user`）：
- `kpi_base` —— KPI 基数
- `phone_allowance` —— 话费满月额度（规则按出勤折算）
- `perfect_attend_amount` —— 全勤奖金额（默认工人 500）
- `expat_daily` —— 外派日额（× EXPAT input）
- `trip_daily` —— 出差日额（× TRIP input）
- `housing_allowance` —— 住房补贴（SG 用，月度固定）
- `overtime` —— 每小时加班费（Monetary）**⚠️ Phase 1 代码未加，Phase 2 开始前先补**

拆分字段（compute store=True）：
- `basic_amount` / `hra_amount` / `medical_amount` / `conveyance_amount`
- 依赖 `wage` + struct type 的三个 pct 字段
- 算法：`hra/med/conv = currency.round(wage × pct)`，`basic = wage − 三者之和`（尾差落 basic）
- 比例全空 → basic = wage，其余 0

展示字段（compute store=False）：
- `daily_wage` —— `base / working_days_per_month`，base = basic 或 wage（按 absence_base）

### `hr.payslip.input.type` (inherit)

- `unit` Selection (amount / day / hour / percent), default amount —— 仅展示

### `hr.payslip` (inherit)

- `kpi_grade` Selection (A / B / C)
- `kpi_grade_amount` —— compute, depends on kpi_grade + version_id.kpi_base
- `_onchange_kpi_grade` —— 客户端即时同步 KPIBONUS input 行
- `_sync_kpi_grade_input` —— 服务端落库同步（write/create 钩子）
- 写 input 时用 `with_context(tg_payroll_kpi_sync=True)` 跳过冲突约束

### `hr.payslip.input` (inherit)

- `_check_kpi_grade_conflict` —— create/write 钩子：当 code='KPIBONUS' 且 payslip.kpi_grade 非空且 context 没标 sync 时，raise UserError

常量在 [models/hr_payslip.py](models/hr_payslip.py)：
- `KPI_INPUT_CODE = 'KPIBONUS'`
- `KPI_GRADE_RATES = {'A': 1.0, 'B': 0.5, 'C': 0.0}`
- `_KPI_SYNC_CTX = 'tg_payroll_kpi_sync'`

## 5. 视图扩展明细

| 视图文件 | 继承 | 加在哪里 |
|---|---|---|
| `hr_payroll_structure_type_views.xml` | `hr_payroll.hr_payroll_structure_type_view_form` | sheet 内 inside，加 4 个分组（Time Base / Salary Breakdown / Overtime / Late Deduction） |
| `hr_payslip_input_type_views.xml` | form + tree | code 字段后加 unit |
| `hr_version_views.xml` | `hr.hr_contract_template_form_view` | notebook inside 加新 page "Payroll Allowances"（左 Salary Breakdown，右 Standard Allowances），整 page `groups="hr_payroll.group_hr_payroll_user"` |
| `hr_payslip_views.xml` | `hr_payroll.view_hr_payslip_form` | `payslip_run_id` 字段后加 `kpi_grade` + `kpi_grade_amount`（grade 为空时 amount 不可见） |

## 6. 数据预置

`data/hr_payslip_input_type_data.xml` 用 `noupdate="1"`，预置 7 个 input type（见 2.2 表）。

## 7. 待办（Phase 2）

**已完成：**
- ✅ `overtime` 字段补全（`models/hr_version.py` + `views/hr_version_views.xml`）
- ✅ BD_WORKER 结构类型 + 薪资结构 + 全套规则（BASIC/HRA/MEDICAL/CONV/OT/PERF_ATT/ADJ/NIGHT_PAY/PROD_PAY/LATE_DED/ABS_DED/AIT/NET）
- ✅ BD_IN 结构类型 + 薪资结构 + 规则（STIPEND/LATE_DED/ABS_DED/NET；无 AIT）
- ✅ AIT 提取为 `_compute_ait()` 方法，所有 BD 结构（除 BD_IN）共用一行调用
- ✅ NIGHT + PROD 独立 input type，BD_WORKER 规则直读（`amount_select=input`）
- ✅ BD_HQ 结构类型 + 薪资结构 + 规则（BASIC/HRA/MEDICAL/CONV/PHONE_ATT/KPI_PAY/ADJ/LATE_DED/ABS_DED/AIT/NET）
- ✅ BD_FAC.MGMT 结构类型 + 薪资结构 + 规则（BD_HQ 基础上加 OT_PAY）
- ✅ BD_SALES_FT 结构类型 + 薪资结构 + 规则（BASIC/HRA/MEDICAL/CONV/PHONE_ATT/COMM_PAY/ADJ/LATE_DED/ABS_DED/AIT/NET）
- ✅ BD_SALES_CT 结构类型 + 薪资结构 + 规则（BASIC=日薪/PHONE_ATT/COMM_PAY/ADJ/LATE_DED/NET；无 ABS_DED/AIT）
- ✅ COMMISSION input type，关联 BD_SALES_FT + BD_SALES_CT 两个结构

**剩余结构（用户确认后逐套录入）：**
- CN_FT（中国正式）—— 用户说先不做
- CN_CT / SG_MGMT —— 后续

1. **预置 struct type 数据**（按 BD/CN/SG 三国法人 × 9 个结构）
   - 每个填好 working_days、三大项 pct、ot_rate、late_rate_mode、late_fixed_per_minute、absence_base
   - 需要确认 0.7122 的来源 / 该值是否同时适用于 BD_WORKER / BD_IN / BD_SALES_CT / Intern 等所有 fixed 模式结构
2. **预置 salary structures**（每个 struct type 一个 default）
3. **预置 salary rule pool**（公共规则，多结构共享）：
   - `BASIC` / `HRA` / `MEDICAL` / `CONVEYANCE` （读 contract.basic_amount 等）
   - `WAGE_FULL`（CN/SG 用，直接 wage）
   - `DAILY_WAGE`（CT/IN 用，`basic_or_wage / working_days × (working_days − ABS)`）
   - `PHONE_ATTEND`（话费按出勤折算：`phone_allowance × (working_days − ABS) / working_days`）
   - `OT_PAY` (`BASIC / working_days / hours_per_day × OT × ot_rate`)
   - `LATE_DEDUCT`（按 struct type 的 late_rate_mode 二选一计算）
   - `ABS_DEDUCT` (`-(base / working_days) × ABS`，base 按 absence_base)
   - `KPI_BONUS`（读 KPIBONUS input；grade 模式下也已经被同步进 input 了，不用走两条路）
   - `PERFECT_ATTEND` (`ABS == 0 ? perfect_attend_amount : 0`)
   - `EXPAT_PAY` (`expat_daily × EXPAT input`)
   - `TRIP_PAY` (`trip_daily × TRIP input`)
   - `HOUSING` (读 `housing_allowance`)
   - `ADJ`（读 ADJ input）
   - `AIT`（暂时占位 0）
   - `NET`
4. **每个 structure 挂载它要用的 rule**（按 2.x 中表格各结构组合）
5. **AIT 阶梯税表实现**（孟加拉个税月度累计计算，独立规则）

## 8. 安装与测试

```bash
# 启动 Odoo（开发库存在 odoo-bin）
cd /Users/zebin/work/tiger/odoo-19.0+e.20250917
./odoo-bin -c odoo.conf -u tg_payroll -d <db_name>
```

### 8.1 自动化测试与结果输出脚本

- 自动化测试：`custom_addons/tg_payroll/tests/`
  - 说明文档：`custom_addons/tg_payroll/tests/README.md`
  - 主要用例：`custom_addons/tg_payroll/tests/test_tg_payroll_structures.py`
  - 运行（示例）：

```bash
./odoo-bin -c odoo.conf -d <db_name> --test-enable -i tg_payroll --stop-after-init
```

- 人工核对脚本（打印各 rule 结果）：`custom_addons/tg_payroll/scripts/run_tg_payroll_cases.py`
  - 运行（示例）：

```bash
./odoo-bin shell -c odoo.conf -d <db_name> -i tg_payroll < custom_addons/tg_payroll/scripts/run_tg_payroll_cases.py
```

测试要点：
1. 设个 BD struct type，填 hra=0.25, medical=0.15, conveyance=0.10
2. 在该 struct type 下建合同，wage=50000，看 4 个拆分字段是否 25000/12500/7500/5000，且 basic 吸收尾差
3. 比例全空时拆分字段应：basic=50000，其余=0
4. PaySlip 选 kpi_grade=A，kpi_base=10000，看 KPIBONUS input 行是否自动出现 amount=10000
5. 选了 grade 之后再手动加一行 KPIBONUS → 应该报 UserError
6. 清掉 grade，再加 KPIBONUS → 正常

## 9. 用户偏好提示

- 步子迈小，**不要超出范围给惊喜**。Phase 2 等用户主动发老系统再做。
- 写代码默认中文注释；UI 文案英文 + `_()`。
- 不要预置 demo 数据，用户偏好手工录入或后续给定。
- 不主动建 markdown 文档，除非用户要求（本文件就是用户明确要求的）。

## 10. Input 关联约定

**所有薪资结构必须关联五大标准 input**（通过 `input_line_type_ids`）：

| code | XML ID | 说明 |
|---|---|---|
| `ABS` | `tg_payroll.input_type_abs` | 缺勤天数 |
| `LATE` | `tg_payroll.input_type_late` | 迟到小时 |
| `OT` | `tg_payroll.input_type_ot` | 加班小时 |
| `KPIBONUS` | `tg_payroll.input_type_kpi_bonus` | KPI 奖金 |
| `ADJ` | `tg_payroll.input_type_adj` | 调整金额 |

新增结构时在 `hr.payroll.structure` 记录里加：
```xml
<field name="input_line_type_ids" eval="[
    (4, ref('tg_payroll.input_type_abs')),
    (4, ref('tg_payroll.input_type_late')),
    (4, ref('tg_payroll.input_type_ot')),
    (4, ref('tg_payroll.input_type_kpi_bonus')),
    (4, ref('tg_payroll.input_type_adj')),
    <!-- 结构专属 input 接着加 -->
]"/>
```

## 11. 薪资规则编写约定

> 每条有逻辑的薪资规则在 `models/hr_payslip.py` 的 `HrPayslip` 类里对应一个方法，规则 XML 里只写一行调用。

### 已有方法清单

| 方法 | 规则用法 | 说明 |
|---|---|---|
| `_prorate(amount)` | `result = payslip._prorate(version.basic_amount)` | 按合同有效期在 payslip 期间折算（跨月入/离职） |
| `_input_amount(code)` | 内部工具 | 取指定 code 的 input 金额，不存在返回 0 |
| `_compute_ot()` | `result = payslip._compute_ot()` | OT_hours × version.overtime |
| `_compute_perfect_attend()` | `result = payslip._compute_perfect_attend()` | ABS==0 → version.perfect_attend_amount |
| `_compute_adj()` | `result = payslip._compute_adj()` | 直读 ADJ input |
| `_compute_late_ded()` | `result = payslip._compute_late_ded()` | 迟到扣款，读 struct type late_rate_mode 分支 |
| `_compute_abs_ded()` | `result = payslip._compute_abs_ded()` | ABS × (wage / working_days) |
| `_compute_ait()` | `result = payslip._compute_ait()` | 孟加拉 AIT 阶梯税表（含跨月折算） |

**新增结构时**：
- 如果需要已有逻辑 → 直接在规则 XML 里调对应方法
- 如果是全新逻辑 → 先在 `hr_payslip.py` 加方法，再写规则
- AIT 算法变更前**必须让用户核对确认**，再改 `_compute_ait()`

## 12. ⚠️ 不破坏原有算薪流程的硬性要求

> **后续每次新增 / 修改薪资结构、规则、字段，都必须考虑：是否影响用户已经在跑的算薪流程？如果会有影响，必须先告诉用户、确认后才能动手，不能擅自改。**
>
> 包括但不限于：
> - 已存在的合同字段语义变更（如 `wage` 含义改变）
> - 已存在的 input type code 修改 / 重命名
> - 已存在的 salary rule 公式调整
> - 旧数据的迁移要求
>
> 即使技术上更"干净"，只要会让线上 payslip 算出与老系统不一致的数字，就**必须先确认**。

## 13. 老系统结构映射表（Phase 2 录入时参考）

记录每套老系统薪资结构的规则、公式、所需 input、可复用的 Phase 1 基础设施。后续录入相同公式的结构时可以直接复用规则。

### 13.1 BD_WORKER（孟加拉工人）

> **状态**：分析完成，待用户确认 wage 语义后录入。

#### 老系统规则清单

| # | 规则名 | category | 公式核心 | 仅 BD_WORKER? |
|---|---|---|---|---|
| 1 | Basic / Contract Payment | BASIC | `wage × active_days / total_days` | 跨结构通用模式 |
| 2 | Late Deduction | DED | `-LATE_hours × 60 × 0.7122` | 跨结构通用模式 |
| 3 | Night Shift Allowance | ALW | input 直读 | 仅工人 |
| 4 | Production Award | ALW/EAR | input 直读 | 仅工人 |
| 5 | Attendance Bonus | ALW | `ABS == 0 ? 500 : 0` | 仅工人 |
| 6 | Conveyance | ALW | `wage × 0.10 × active/total` | BD 系列通用 |
| 7 | House Rent | ALW | `wage × 0.25 × active/total` | BD 系列通用 |
| 8 | Medical | ALW | `wage × 0.15 × active/total` | BD 系列通用 |
| 9 | Absence Deduction | DED | `-ABS_days × wage / 26` | 跨结构通用模式 |
| 10 | Adjustment | EAR/DED | input ADJ 直读 | 跨结构通用 |
| 11 | AIT (Income Tax) | DED | 阶梯税表，年度 `wage × 13`，男女不同税阶 | BD 系列通用 |
| 12 | Net Salary | NET | `BASIC + ALW + DED + EAR` 汇总 | Odoo 标准 |

#### Input 需求

| code | 单位 | 来源 | 备注 |
|---|---|---|---|
| `ABS_D`（老） / `ABS`（我们预置） | 天 | 导入 | **待确认 code** |
| `LATE` | 小时 | 导入 | 已预置 |
| `OT` | 小时 | （工人也可能有，老系统未列）| 已预置 |
| `NIGHT` | 金额 | 导入 | **待预置或塞 ADJ** |
| `PROD` | 金额 | 导入 | **待预置或塞 ADJ** |
| `ADJ` | 金额 | 导入 | 已预置 |

#### 老系统的 wage 语义（关键差异）

老系统：`wage = BASIC = 100%`，HRA/Med/Conveyance **叠加**在 wage 之上。
即一个"月薪 10000"的工人，实际应发 ≈ 10000 × 1.5 = 15000（再加加班/全勤）。

Phase 1 设计：`wage = GROSS`，BASIC 占 50%，三大项占 50%，合计 100%。

→ **不兼容，必须二选一**（待用户拍板）：
- **方案 A**：迁移时把 `wage` 改为 `老 wage × 1.5`（数据迁移，业务逻辑保持干净）
- **方案 B**：改 Phase 1 — basic_amount = wage、三大项是叠加项不是拆分；去掉"TOTAL = WAGE"约束
- **方案 C**：BD 走老语义、CN/SG 走我们的语义（双轨，Phase 1 字段对 BD 不用）

#### 跨月入职/离职按天比例（Phase 1 没做）

老系统所有主薪+三大项规则都用 `(amount / total_days) × active_days` 处理：
- `total_days = (date_to - date_from).days + 1`（payslip 自然天数）
- `active_days = (min(contract_end, date_to) - max(contract_start, date_from)).days + 1`

Phase 2 在规则代码里加，不需要改 Phase 1 的 compute 字段（因为 compute 字段不知道 payslip 期间）。
意味着 BD 系列的主薪/三大项规则**不能直接用 `contract.basic_amount`**，要用 `contract.wage × pct × active/total` 自己算。

#### AIT 阶梯税表（孟加拉个税）

```
annual_income = wage × 13            # 包含 1 个月节日奖金
tax_free      = min(annual_income/3, 450000)
taxable       = annual_income - tax_free

# 男性税阶
slabs_male   = [(350000, 0), (100000, 5%), (400000, 10%), (500000, 15%), (500000, 20%), (2000000, 25%)]
# 女性税阶
slabs_female = [(400000, 0), ...其余同男]

# 超过累计 3850000 / 3900000 之上一律 25%
# 计算后扣除返点：rebate = taxable × 3%
# annual_tax = max(tax - rebate, 5000)
# monthly_tax = annual_tax / 12
```

→ Phase 2 实现独立规则 `AIT`，在 BD 系列共享。
→ `× 13` 暗示有 1 个月节日奖金，**待确认**：是否在合同上加 `festival_bonus_months` 字段（默认 1），还是硬编码？
→ 用 `employee.gender`（Odoo 19 `hr.employee` 应有此字段）。

#### 复用 Phase 1 的清单

| Phase 1 设施 | BD_WORKER 用法 |
|---|---|
| `struct_type.working_days_per_month = 26` | 缺勤、迟到、加班 base |
| `struct_type.late_rate_mode = fixed` | 迟到模式 |
| `struct_type.late_fixed_per_minute = 0.7122` | 迟到费率 |
| `struct_type.absence_base = wage` | 缺勤按 wage/26 |
| `struct_type.ot_rate = 2.0` | 工人也有加班（待确认） |
| `struct_type.hra_pct / medical_pct / conveyance_pct` | 取决于 wage 语义方案 |
| `contract.perfect_attend_amount = 500` | 全勤奖默认 |
| `contract.basic_amount` 等 4 个 compute | **不直接用**（要做跨月按比例） |
| `input ADJ` | 复用 |
| `input ABS / LATE / OT` | 复用（ABS 待对齐 code） |
| `input NIGHT / PROD` | **待预置** |

#### 待用户确认的问题（动工前必答）

1. ✅ **wage 语义**：新系统 BD_WORKER 同 Full Time Employment CSV — `wage = GROSS`，`BASIC = wage × 50%`，total = 100%。与 Phase 1 设计一致。
2. **ABS code**：我们预置是 `ABS`，老系统 BD_WORKER 用 `ABS_D`。**新系统用哪个？** 未确认。
3. **Night Shift / Production Award**：独立 input（NIGHT/PROD）还是暂塞 ADJ？**未确认。**
4. **Festival bonus**：AIT 公式里 `wage × 13`，`× 13` 是硬编码还是加合同字段？**未确认。**
5. ✅ **迟到费率**：所有结构统一使用动态费率（`wage / (working_days × hours_per_day × 60)`），0.7122 废弃。
6. ✅ **工人有加班**：有。OT 公式 = `OT_hours × contract.overtime`（overtime 字段在合同，Monetary）。

