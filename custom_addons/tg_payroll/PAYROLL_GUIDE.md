# Tiger 薪资体系说明

> 本文档面向 HR / 财务，介绍系统已预置的 9 套薪资结构、计算规则、以及每月算薪需要录入的内容。
>
> 阅读路径建议：先看 §1 总览 → §2 速览公式 → §3 通用计算规则 → §4 找到自己负责的结构看详情 → §5 / §6 速查。

---

## 1. 总览

系统已预置 **9 套薪资结构**，覆盖三个国家主体：

| 国家 | 结构数量 | 包含结构 |
|---|---|---|
| 🇧🇩 孟加拉（BD） | 6 | BD_HQ、BD_FAC.MGMT、BD_SALES_FT、BD_SALES_CT、BD_WORKER、BD_IN |
| 🇨🇳 中国（CN） | 2 | CN_FT、CN_CT |
| 🇸🇬 新加坡（SG） | 1 | SG_MGMT |

每个员工按其岗位/合同类型选择对应的结构，系统会自动按规则算薪。

---

## 2. 速览：每套结构的发放公式

| 结构 | 适用人群 | 发放公式 |
|---|---|---|
| **BD_HQ** | 孟加拉本地职能 | Basic + 三大项 + 话费 + KPI + 调整 − 迟到 − 缺勤 − 个税 |
| **BD_FAC.MGMT** | 工厂管理层/职能 | Basic + 三大项 + 话费 + KPI + **加班** + 调整 − 迟到 − 缺勤 − 个税 |
| **BD_SALES_FT** | 销售全职 | Basic + 三大项 + 话费 + **提成** + 调整 − 迟到 − 缺勤 − 个税 |
| **BD_SALES_CT** | 销售外包（日薪） | 月薪（按出勤折算）+ 话费 + 提成 + 调整 − 迟到 − 缺勤 |
| **BD_WORKER** | 工人 | Basic + 三大项 + 加班 + **全勤奖** + **夜班费** + **产量奖** + 调整 − 迟到 − 缺勤 − 个税 |
| **BD_IN** | 实习生 | 月薪（按出勤折算）− 迟到 − 缺勤 |
| **CN_FT** | 中国正式 | 月薪 + 外派津贴 + 出差补助 + KPI − 缺勤 |
| **CN_CT** | 中国外包 | 月薪 ÷ 26 × 出勤天数 |
| **SG_MGMT** | 新加坡管理层 | 月薪 + 外派津贴 + KPI + 住房补贴 |

> **说明**：「三大项」= House Rent Allowance（HRA）+ Medical + Conveyance，BD 系列固定按 Wage 的 25%/15%/10% 拆分。

---

## 3. 通用计算规则

下面是各项的计算逻辑，所有结构共用同一套口径。

### 3.1 Basic（基本工资）

按合同类型分两种取值方式：

- **拆分型**（BD_HQ / BD_FAC.MGMT / BD_SALES_FT / BD_WORKER）  
  Basic = Wage × 50%
- **整额型**（BD_IN / BD_SALES_CT / CN_FT / SG_MGMT）  
  Basic = Wage（不拆）

两种方式都会按合同在该薪资期内的有效天数折算（处理跨月入/离职，详见 §7.1）。

### 3.2 三大项（House Rent / Medical / Conveyance）

仅 BD 拆分型结构有，按 Wage 固定比例：

| 项 | 比例 |
|---|---|
| House Rent Allowance（HRA） | Wage × 25% |
| Medical Allowance | Wage × 15% |
| Conveyance Allowance | Wage × 10% |

> 系统保证 **Basic + HRA + Medical + Conveyance = Wage**（小数尾差落 Basic）。
> 同样会按合同有效天数折算。

### 3.3 话费津贴（Phone Allowance）

合同上配置「Phone Allowance（满月额度）」字段，发放时按合同有效天数折算。

### 3.4 加班费（Overtime Pay）

```
加班费 = OT 小时数 × 合同上的「Overtime Rate / Hour」（每小时加班费）
```

- 加班时薪在每位员工合同上单独配置（合同字段：Overtime Rate / Hour）
- 当月加班小时数从 PAYSLIP 的 **OT input** 录入

### 3.5 全勤奖（Perfect Attendance Bonus）

```
若 ABS = 0 → 发放 = 合同上的「Perfect Attendance Bonus」金额
若 ABS > 0 → 不发
```

- 默认金额 500 BDT（可在合同字段调整）
- 仅 BD_WORKER 启用

### 3.6 KPI 奖金（KPI Bonus）

**两种录入方式（任选其一）**：

| 方式 | 操作 | 适用场景 |
|---|---|---|
| ① 直接录金额 | 在 PAYSLIP 的 INPUT 表里加 KPIBONUS 金额 | 临时金额、导入 |
| ② 按等级计算 | 在 PAYSLIP 上选 KPI Grade（A/B/C），系统自动算 | 标准化考核 |

**等级映射**：A = 100% × 合同 KPI Base、B = 50%、C = 0%

> ⚠️ 选了 KPI Grade 后系统会自动写入 KPIBONUS input，此时**禁止手动改 KPIBONUS**（会报错）。如要切回手动模式，先清掉 KPI Grade。

### 3.7 外派津贴 / 出差补助（Expat / Trip）

```
外派津贴 = EXPAT 天数 × 合同「Expat Allowance / Day」
出差补助 = TRIP  天数 × 合同「Business Trip Allowance / Day」
```

- 日额在合同上配置
- 天数从 PAYSLIP 对应 input 录入

### 3.8 住房补贴（Housing Allowance，仅 SG）

合同上配置月度固定金额，发放时按合同有效天数折算。

### 3.9 销售提成（Commission）

直接录金额到 PAYSLIP 的 **COMMISSION input**，按录入金额发放，不参与计算。

### 3.10 夜班费 / 产量奖（仅 BD_WORKER）

直接录金额到 PAYSLIP 的 **NIGHT / PROD input**，按录入金额发放，不参与计算。

### 3.11 调整金额（Adjustment）

直接录金额（可正可负）到 PAYSLIP 的 **ADJ input**。用于一次性补/扣，不归类到上面任何一项时使用。

### 3.12 迟到扣款（Late Deduction）

按结构分两种模式（系统已预先配好）：

| 模式 | 适用结构 | 每分钟扣款 |
|---|---|---|
| **按本人月薪算** | BD_HQ、BD_FAC.MGMT、BD_SALES_FT、BD_WORKER、CN_FT、SG_MGMT | Wage ÷ (26 × 8 × 60) |
| **固定费率** | BD_IN、BD_SALES_CT | 0.7122 BDT / 分钟 |

```
迟到扣款 = − 迟到小时 × 60 × 每分钟扣款
```

迟到小时数从 PAYSLIP 的 **LATE input** 录入。

### 3.13 缺勤扣款（Absence Deduction）

```
缺勤扣款 = − ABS 天数 × (Wage ÷ 26)
```

缺勤天数从 PAYSLIP 的 **ABS input** 录入。

### 3.14 个税 AIT（仅孟加拉，BD_HQ/FAC/SALES_FT/WORKER）

按孟加拉 NBR 阶梯税率计算，分性别税阶（系统自动读 Employee 上的 Gender）。

```
年度应税收入 = Wage × 13            （含 1 个月 Eid Bonus）
免税额       = min(年收入 ÷ 3, 450,000)
应税额       = 年收入 − 免税额
```

**男性税阶**：

| 应税额区间 | 税率 |
|---|---|
| 0 – 350,000 | 0% |
| 350,000 – 450,000 | 5% |
| 450,000 – 850,000 | 10% |
| 850,000 – 1,350,000 | 15% |
| 1,350,000 – 1,850,000 | 20% |
| 1,850,000 – 3,850,000 | 25% |
| 3,850,000 以上 | 25% |

**女性税阶**：起征点为 400,000（其余同男性）。

```
年度税前 = Σ（每档应税额 × 税率）
年度税  = max(年度税前 × 97%, 5,000)         （3% 抵扣，最低 5000）
月度税  = 年度税 ÷ 12，再按合同有效天数折算
```

> ⚠️ 公式硬编码 ×13（含 1 个月 Eid Bonus 假设），如未来奖金月数有变需要改代码。

### 3.15 实发工资（Net Salary）

```
Net = Basic + 所有津贴(ALW) + 所有扣款(DED)
```

---

## 4. 各结构详情

### 4.1 BD_HQ（孟加拉本地职能）

**发放公式**

```
Basic + HRA + Medical + Conveyance + 话费 + KPI + 调整 − 迟到 − 缺勤 − AIT
```

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数（用于缺勤扣款） |
| LATE | 迟到小时（用于迟到扣款） |
| OT | 加班小时（**当前规则未启用，预留**） |
| KPIBONUS | KPI 奖金金额（也可由 KPI Grade 自动算） |
| ADJ | 调整金额 |

**合同要配置的字段**：Wage、Phone Allowance、KPI Base（用 Grade 时）

---

### 4.2 BD_FAC.MGMT（工厂管理层/职能）

**发放公式**

```
Basic + HRA + Medical + Conveyance + 话费 + KPI + 加班 + 调整 − 迟到 − 缺勤 − AIT
```

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数 |
| LATE | 迟到小时 |
| OT | 加班小时（**已启用**，× 合同加班时薪） |
| KPIBONUS | KPI 奖金金额 |
| ADJ | 调整金额 |

**合同要配置的字段**：Wage、Phone Allowance、KPI Base、Overtime Rate / Hour

---

### 4.3 BD_SALES_FT（销售全职）

**发放公式**

```
Basic + HRA + Medical + Conveyance + 话费 + 提成 + 调整 − 迟到 − 缺勤 − AIT
```

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数 |
| LATE | 迟到小时 |
| OT | 加班小时（**预留未启用**） |
| KPIBONUS | KPI（**预留未启用**，销售用提成不用 KPI） |
| ADJ | 调整金额 |
| COMMISSION | 销售提成金额 |

**合同要配置的字段**：Wage、Phone Allowance

---

### 4.4 BD_SALES_CT（销售外包，日薪）

**发放公式**

```
月薪（按合同有效天数折算）+ 话费 + 提成 + 调整 − 迟到 − 缺勤
```

> 不拆分三大项，**没有 AIT**（外包不代扣）。

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数 |
| LATE | 迟到小时（**固定费率 0.7122/分钟**） |
| OT | 加班小时（**预留未启用**） |
| KPIBONUS | KPI（**预留未启用**） |
| ADJ | 调整金额 |
| COMMISSION | 销售提成金额 |

**合同要配置的字段**：Wage、Phone Allowance

---

### 4.5 BD_WORKER（工人）

**发放公式**

```
Basic + HRA + Medical + Conveyance + 加班 + 全勤奖
+ 夜班费 + 产量奖 + 调整
− 迟到 − 缺勤 − AIT
```

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数（影响缺勤扣款 + 全勤奖） |
| LATE | 迟到小时 |
| OT | 加班小时 |
| KPIBONUS | KPI（**预留未启用**） |
| ADJ | 调整金额 |
| NIGHT | 夜班费金额 |
| PROD | 产量奖金额 |

**合同要配置的字段**：Wage、Overtime Rate / Hour、Perfect Attendance Bonus（默认 500）

---

### 4.6 BD_IN（实习生）

**发放公式**

```
月薪（按合同有效天数折算）− 迟到 − 缺勤
```

> 不拆分三大项，**没有 AIT**，迟到用**固定费率 0.7122/分钟**。

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数 |
| LATE | 迟到小时（固定费率） |
| OT | 加班小时（**预留未启用**） |
| KPIBONUS | KPI（**预留未启用**） |
| ADJ | 调整（**预留未启用**） |

**合同要配置的字段**：Wage

---

### 4.7 CN_FT（中国正式）

**发放公式**

```
月薪 + 外派津贴 + 出差补助 + KPI − 缺勤
```

> 不拆分三大项；**没有迟到扣款、没有个税**（中国个税不在此计算）。

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数（用于缺勤扣款） |
| LATE | 迟到小时（**预留未启用**） |
| OT | 加班小时（**预留未启用**） |
| KPIBONUS | KPI 奖金（也可由 KPI Grade 自动算） |
| ADJ | 调整（**预留未启用**） |
| EXPAT | 外派天数（× 合同日额） |
| TRIP | 出差天数（× 合同日额） |

**合同要配置的字段**：Wage、Expat Allowance / Day、Business Trip Allowance / Day、KPI Base

---

### 4.8 CN_CT（中国外包）

**发放公式**

```
月薪 ÷ 26 × 出勤天数        （出勤天数 = 26 − ABS 天数）
```

> 极简，**只算工作天数**，没有任何扣项。

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS | 缺勤天数（用于扣减出勤天数） |
| LATE / OT / KPIBONUS / ADJ | **预留未启用** |

**合同要配置的字段**：Wage

---

### 4.9 SG_MGMT（新加坡管理层）

**发放公式**

```
月薪 + 外派津贴 + KPI + 住房补贴
```

> 不拆分三大项，**没有任何扣款**（新加坡个税年度自行申报，不代扣）。

**可用 INPUT**

| INPUT | 用途 |
|---|---|
| ABS / LATE / OT / ADJ / TRIP | **预留未启用** |
| KPIBONUS | KPI 奖金（也可由 KPI Grade 自动算） |
| EXPAT | 外派天数（× 合同日额） |

**合同要配置的字段**：Wage、Expat Allowance / Day、Housing Allowance、KPI Base

---

## 5. INPUT 速查表

> 所有 INPUT 在 PAYSLIP 的「Salary Inputs」标签里录入；导入也支持。

| Code | 名称 | 单位 | 用途 |
|---|---|---|---|
| `ABS` | Absence | 天 | 缺勤天数 → 缺勤扣款、全勤奖判断、CN_CT 出勤天数 |
| `LATE` | Late | 小时 | 迟到小时 → 迟到扣款 |
| `OT` | Overtime | 小时 | 加班小时 → 加班费 |
| `KPIBONUS` | KPI Bonus | 金额 | KPI 奖金；可由 KPI Grade 自动写入 |
| `ADJ` | Adjustment | 金额 | 调整金额（可正可负） |
| `EXPAT` | Expat Days | 天 | 外派天数 → 外派津贴 |
| `TRIP` | Business Trip Days | 天 | 出差天数 → 出差补助 |
| `NIGHT` | Night Shift Allowance | 金额 | 夜班费（仅 BD_WORKER） |
| `PROD` | Production Award | 金额 | 产量奖（仅 BD_WORKER） |
| `COMMISSION` | Commission | 金额 | 销售提成（仅 BD_SALES_FT/CT） |

---

## 6. 合同字段速查表

| 字段 | 用途 | 哪些结构需要 |
|---|---|---|
| **Wage** | 月薪 | 全部 |
| **Currency** | 币种（决定金额单位） | 全部 |
| **Overtime Rate / Hour** | 每小时加班费 | BD_FAC.MGMT、BD_WORKER |
| **Phone Allowance** | 满月话费额度 | BD_HQ、BD_FAC.MGMT、BD_SALES_FT、BD_SALES_CT |
| **Perfect Attendance Bonus** | 全勤奖金额（默认 500） | BD_WORKER |
| **KPI Base** | KPI 奖金基数 | 用 KPI Grade 的：BD_HQ、BD_FAC.MGMT、CN_FT、SG_MGMT |
| **Expat Allowance / Day** | 外派日额 | CN_FT、SG_MGMT |
| **Business Trip Allowance / Day** | 出差日额 | CN_FT |
| **Housing Allowance** | 月度住房补贴 | SG_MGMT |

> 合同上还会自动展示 4 个**只读拆分字段**（Basic / HRA / Medical / Conveyance）和 1 个**只读日薪字段**（Daily Wage），方便核对，无需手填。

---

## 7. 重要约定

### 7.1 跨月入职 / 离职：按天数自动折算

凡是**按月发放**的项目（Basic、三大项、话费、住房补贴），系统会按合同在该薪资期内的实际生效天数自动折算：

```
实发金额 = 满月金额 × 合同有效天数 / 薪资周期总天数
```

**例**：员工合同 5 月 15 日入职，5 月薪资周期 5/1 ~ 5/31（共 31 天），合同有效 17 天（5/15 ~ 5/31），则：

- Basic 实发 = 满月 Basic × 17 / 31 ≈ 满月的 54.84%

> 注：**按实际录入的项目**（缺勤、迟到、加班、KPI、调整、津贴天数等）不会再次折算 —— 录入是多少就发多少。

### 7.2 KPI 两种模式不能混用

每张 PAYSLIP 上 KPI 二选一：

- 选了 KPI Grade → 系统自动写 KPIBONUS，**手动改 / 导入 KPIBONUS 会报错**
- 没选 KPI Grade → 走手动 / 导入 KPIBONUS

切换：清掉 Grade 即可恢复手动。

### 7.3 缺勤天数固定按 26 天月度基数计算

无论当月自然天数是 28 / 30 / 31，缺勤扣款的日薪 = Wage ÷ 26、迟到扣款的时薪 = Wage ÷ (26 × 8)。这是行业统一口径，已固化在系统配置里。

### 7.4 工作天数 / 出勤天数定义

- **工作天数**：固定 26 天/月（系统配置，不随自然月变）
- **出勤天数** = 26 − ABS 天数（仅 CN_CT 直接用这个数算薪）

### 7.5 「预留未启用」的含义

每套结构在录 INPUT 时都允许选某些 INPUT，但当前规则可能没有用到（标注为「预留未启用」）。这意味着：

- 录了也没用，不会出现在算薪结果里
- 是给未来扩展留口子，避免到时候再改结构定义
- 如果需要启用，找开发加规则即可（不需要改 INPUT 配置）

---

## 8. 常见操作

| 想做 | 操作 |
|---|---|
| 看员工本月实发 | PAYSLIP → 选员工 → Compute Sheet |
| 录当月缺勤 | PAYSLIP → Salary Inputs → 加一行 ABS，填天数 |
| 录当月加班 | PAYSLIP → Salary Inputs → 加一行 OT，填小时 |
| KPI 按等级发 | PAYSLIP 上选 KPI Grade（A/B/C） |
| 临时补/扣一笔 | PAYSLIP → Salary Inputs → 加一行 ADJ，填金额（可正可负） |
| 改员工话费额度 | 员工合同 → Payroll Allowances → 改 Phone Allowance |
| 改加班时薪 | 员工合同 → Payroll Allowances → 改 Overtime Rate / Hour |
| 看三大项拆分明细 | 员工合同 → Payroll Allowances → 左侧 Salary Breakdown |

---

## 9. 联系方式

如果发现：
- 计算结果与预期不符
- 需要新增 INPUT / 字段 / 结构
- 政策调整（如 AIT 税率、月度工作天数）

请联系开发团队（Tiger-Zebin）确认。
