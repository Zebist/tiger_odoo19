# tg_payroll tests

本目录包含 `tg_payroll` 的自动化测试与人工核对辅助脚本说明。

## 1) 自动化测试（Odoo test）

测试文件：
- `test_tg_payroll_structures.py`

覆盖内容（概要）：
- 9 套薪资结构的核心规则计算（按 `compute_sheet()` 生成 payslip lines，再断言每条 rule 的 `total`）
- 关键特殊场景：
  - 月中入职 / 月中离职：验证 `_prorate()` 的自然日折算
  - KPI grade：验证 payslip 上选择 grade 后自动同步 `KPIBONUS` input，并由规则读取
  - CN_CT：验证按 \(wage/26 × (26-ABS)\) 的口径计算
- AIT：只做“行级别性质断言”（应为非正值），不做精确税额断言（避免算法迭代导致测试频繁波动）

运行（示例）：

```bash
./odoo-bin -c odoo.conf -d <db_name> --test-enable -i tg_payroll --stop-after-init
```

按 tag 精确运行（推荐，只跑 `tg_payroll`，不会跑官方其它模块测试）：

```bash
# 模块已安装时（最常见）：用 -u（update）确保进入 post tests
./odoo-bin -c odoo.conf -d <db_name> --test-enable --test-tags "tg_payroll" -u tg_payroll --stop-after-init

# 模块尚未安装时：用 -i（install）
./odoo-bin -c odoo.conf -d <db_name> --test-enable --test-tags "tg_payroll" -i tg_payroll --stop-after-init
```

说明：
- 测试用例使用 `post_install`（本仓库的启动/安装流程会进入 post tests 阶段），因此以 post tests 方式执行。
- Odoo 在 post tests 阶段只会处理“本次实际安装/更新过”的模块（`registry.updated_modules`）。
  如果你 `-i tg_payroll` 但模块已安装，updated_modules 不会包含它，post-tests 会显示 0 —— 这就是为什么推荐已安装时用 `-u`。

补充：
- `--test-tags "/tg_payroll"` 在 Odoo 的 tag selector 会隐式要求 `standard`，并且受 test position 过滤影响更大；
  若你只想跑自定义模块用例，优先用上面的 `--test-tags "tg_payroll"`。

## 2) 人工核对脚本（打印结果）

脚本：
- `../scripts/run_tg_payroll_cases.py`

用途：
- 在数据库中创建临时 employee/version/payslip，执行 `compute_sheet()` 后把每条 payslip line 打印出来，方便肉眼核对。

运行（示例）：

```bash
# 注意：必须在“真实终端 shell”里执行，让 `< ...py` 的 stdin 重定向生效。
# 如果你是在 IDE 的 Run/Debug（非 shell）里跑，`<` 会被当作参数传给 odoo-bin，从而报错。
./odoo-bin shell -c odoo.conf -d <db_name> -i tg_payroll < custom_addons/tg_payroll/scripts/run_tg_payroll_cases.py

# IDE 场景可用（通过 bash 包一层，让重定向由 shell 处理）：
bash -lc "./odoo-bin shell -c odoo.conf -d <db_name> -i tg_payroll < custom_addons/tg_payroll/scripts/run_tg_payroll_cases.py"
```

