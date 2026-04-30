# -*- coding: utf-8 -*-
"""
用法（在项目根目录执行）：

./odoo-bin shell -c odoo.conf -d <db_name> -i tg_payroll < custom_addons/tg_payroll/scripts/run_tg_payroll_cases.py

说明：
- 这是一个“结果输出脚本”，方便人工核对各结构的规则金额。
- 脚本会在当前数据库中创建临时员工/合同(version)/payslip 并 compute_sheet()，然后打印每条 payslip line。
"""

from datetime import date

from odoo import Command


def _fmt(amount, currency):
    return "%s %s" % (currency.name, currency.round(amount))


def _print_lines(slip):
    print("\n=== %s ===" % slip.name)
    for line in slip.line_ids.sorted('sequence'):
        print("%-12s %-28s %s" % (line.code, line.name, _fmt(line.total, slip.currency_id)))
    print("NET (field) :", _fmt(slip.net_wage, slip.currency_id))


def _create_slip(env, struct_xmlid, emp_name, wage, date_from, date_to, *, inputs=None, version_vals=None, kpi_grade=None):
    struct = env.ref(struct_xmlid)
    st = struct.type_id
    emp = env['hr.employee'].create({
        'name': emp_name,
        'sex': 'male',
        'date_version': date_from,
        'contract_date_start': date_from,
        'contract_date_end': date(2027, 12, 31),
        'wage': wage,
        'structure_type_id': st.id,
    })
    emp.resource_calendar_id = env.company.resource_calendar_id

    version = emp.version_id
    if version_vals:
        version.write(version_vals)

    input_cmds = []
    for code, amount in (inputs or {}).items():
        it = env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
        if not it:
            raise RuntimeError("Missing input type %s" % code)
        input_cmds.append(Command.create({
            'input_type_id': it.id,
            'amount': amount,
            'name': it.name,
        }))

    slip = env['hr.payslip'].create({
        'name': '%s %s' % (emp.name, struct.name),
        'employee_id': emp.id,
        'version_id': version.id,
        'struct_id': struct.id,
        'date_from': date_from,
        'date_to': date_to,
        'input_line_ids': input_cmds,
        'kpi_grade': kpi_grade,
    })
    if kpi_grade:
        slip.action_apply_kpi_grade()
    slip.compute_sheet()
    return slip


def main(env):
    env.user.group_ids |= env.ref('hr_payroll.group_hr_payroll_manager')

    slips = []
    slips.append(_create_slip(
        env,
        'tg_payroll.tg_struct_bd_worker',
        'BD Worker',
        26000.0,
        date(2026, 4, 1), date(2026, 4, 30),
        inputs={'ABS': 2, 'LATE': 1, 'OT': 10, 'ADJ': 50, 'NIGHT': 200, 'PROD': 300},
        version_vals={'overtime': 100.0, 'perfect_attend_amount': 500.0},
    ))
    slips.append(_create_slip(
        env,
        'tg_payroll.tg_struct_cn_ft',
        'CN FT',
        26000.0,
        date(2026, 4, 1), date(2026, 4, 30),
        inputs={'ABS': 2, 'EXPAT': 3, 'TRIP': 2},
        version_vals={'kpi_base': 10000.0, 'expat_daily': 100.0, 'trip_daily': 50.0},
        kpi_grade='A',
    ))
    slips.append(_create_slip(
        env,
        'tg_payroll.tg_struct_cn_ct',
        'CN CT',
        26000.0,
        date(2026, 4, 1), date(2026, 4, 30),
        inputs={'ABS': 2},
    ))
    slips.append(_create_slip(
        env,
        'tg_payroll.tg_struct_sg_mgmt',
        'SG MGMT',
        30000.0,
        date(2026, 4, 1), date(2026, 4, 30),
        inputs={'EXPAT': 5},
        version_vals={'kpi_base': 12000.0, 'expat_daily': 200.0, 'housing_allowance': 5000.0},
        kpi_grade='B',
    ))

    for slip in slips:
        _print_lines(slip)


main(env)

