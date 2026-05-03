# pyright: ignore
# -*- coding: utf-8 -*-
from datetime import date

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('tg_payroll', 'standard', 'post_install', '-at_install')
class TestTGPayrollStructures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_manager')

        cls.currency = cls.env.company.currency_id
        cls.calendar = cls.env.company.resource_calendar_id

        cls.structs = {
            'BD_WORKER': cls.env.ref('tg_payroll.tg_struct_bd_worker'),
            'BD_IN': cls.env.ref('tg_payroll.tg_struct_bd_intern'),
            'BD_HQ': cls.env.ref('tg_payroll.tg_struct_bd_hq'),
            'BD_FAC.MGMT': cls.env.ref('tg_payroll.tg_struct_bd_fac_mgmt'),
            'BD_SALES_FT': cls.env.ref('tg_payroll.tg_struct_bd_sales_ft'),
            'BD_SALES_CT': cls.env.ref('tg_payroll.tg_struct_bd_sales_ct'),
            'CN_FT': cls.env.ref('tg_payroll.tg_struct_cn_ft'),
            'CN_CT': cls.env.ref('tg_payroll.tg_struct_cn_ct'),
            'SG_MGMT': cls.env.ref('tg_payroll.tg_struct_sg_mgmt'),
        }

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _create_employee(self, name, structure_type, wage):
        emp = self.env['hr.employee'].create({
            'name': name,
            'sex': 'male',
            'date_version': date(2026, 4, 1),
            'contract_date_start': date(2026, 4, 1),
            'contract_date_end': date(2027, 3, 31),
            'wage': wage,
            'structure_type_id': structure_type.id,
        })
        emp.resource_calendar_id = self.calendar
        return emp

    def _create_payslip(self, employee, struct, date_from, date_to, *,
                        inputs=None, version_vals=None, kpi_grade=None):
        version = employee.version_id
        if version_vals:
            version.write(version_vals)

        input_cmds = []
        for code, amount in (inputs or {}).items():
            it = self.env['hr.payslip.input.type'].search([('code', '=', code)], limit=1)
            self.assertTrue(it, "Missing input type for code %s" % code)
            input_cmds.append(Command.create({
                'input_type_id': it.id,
                'amount': amount,
                'name': it.name,
            }))

        run = self.env['hr.payslip.run'].create({
            'name': 'TG Structure Test %s' % employee.name,
            'date_start': date_from,
            'date_end': date_to,
            'structure_id': struct.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': '%s %s' % (employee.name, struct.name),
            'employee_id': employee.id,
            'version_id': version.id,
            'struct_id': struct.id,
            'payslip_run_id': run.id,
            'date_from': date_from,
            'date_to': date_to,
            'input_line_ids': input_cmds,
            'kpi_grade': kpi_grade,
        })
        # KPI Grade 同步现已改为按钮触发，测试需显式调用一次
        if kpi_grade:
            slip.action_apply_kpi_grade()
        slip.compute_sheet()
        return slip

    def _line_total(self, slip, code):
        line = slip.line_ids.filtered(lambda l: l.code == code)
        self.assertTrue(line, "Missing line %s on payslip %s" % (code, slip.name))
        return sum(line.mapped('total'))

    # ---------------------------------------------------------------------
    # Tests: base cases per structure
    # ---------------------------------------------------------------------

    def test_bd_worker_base_case(self):
        struct = self.structs['BD_WORKER']
        st = struct.type_id
        emp = self._create_employee('BD Worker', st, 26000.0)
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            inputs={
                'ABS': 2,
                'LATE': 1,   # hours
                'OT': 10,    # hours
                'ADJ': 50,
                'NIGHT': 200,
                'PROD': 300,
            },
            version_vals={
                'overtime': 100.0,
                'perfect_attend_amount': 500.0,
            }
        )

        # breakdown: wage=26000, pct 25/15/10 -> HRA=6500, MED=3900, CONV=2600, BASIC=13000
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), 13000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'HRA'), 6500.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'MEDICAL'), 3900.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'CONV'), 2600.0, places=2)

        # inputs driven
        self.assertAlmostEqual(self._line_total(slip, 'OT_PAY'), 1000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'NIGHT_PAY'), 200.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'PROD_PAY'), 300.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'ADJ'), 50.0, places=2)

        # absence / late deductions
        self.assertAlmostEqual(self._line_total(slip, 'ABS_DED'), -(26000.0 / 26.0) * 2, places=2)
        # late = -(60 minutes) * (wage / (26*8*60))  since wage_based
        self.assertAlmostEqual(self._line_total(slip, 'LATE_DED'), -(60.0) * (26000.0 / (26.0 * 8.0 * 60.0)), places=2)

        # perfect attendance should be 0 because ABS != 0
        self.assertAlmostEqual(self._line_total(slip, 'PERF_ATT'), 0.0, places=2)

        # AIT is a negative number (we don't assert exact value here)
        self.assertLessEqual(self._line_total(slip, 'AIT'), 0.0)

        # NET = sum categories
        self.assertAlmostEqual(self._line_total(slip, 'NET'), slip.net_wage, places=2)

    def test_bd_sales_ct_has_abs_ded(self):
        struct = self.structs['BD_SALES_CT']
        st = struct.type_id
        emp = self._create_employee('BD Sales CT', st, 26000.0)
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            inputs={'ABS': 1, 'LATE': 0, 'ADJ': 0, 'COMMISSION': 0},
        )
        self.assertAlmostEqual(self._line_total(slip, 'ABS_DED'), -(26000.0 / 26.0) * 1, places=2)

    def test_cn_ft_kpi_grade_sync_and_trip_expat(self):
        struct = self.structs['CN_FT']
        st = struct.type_id
        emp = self._create_employee('CN FT', st, 26000.0)
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            inputs={'ABS': 2, 'EXPAT': 3, 'TRIP': 2},
            version_vals={'kpi_base': 10000.0, 'expat_daily': 100.0, 'trip_daily': 50.0},
            kpi_grade='A',
        )

        # basic is wage (no breakdown for CN_FT type) prorated full month => 26000
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), 26000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'EXPAT_PAY'), 300.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'TRIP_PAY'), 100.0, places=2)

        # KPI grade A => 100% of base, synced into KPIBONUS input and read by KPI_PAY rule
        self.assertAlmostEqual(self._line_total(slip, 'KPI_PAY'), 10000.0, places=2)

        # ABS deduction exists for CN_FT
        self.assertAlmostEqual(self._line_total(slip, 'ABS_DED'), -(26000.0 / 26.0) * 2, places=2)

    def test_cn_ct_attendance_26_minus_abs(self):
        struct = self.structs['CN_CT']
        st = struct.type_id
        emp = self._create_employee('CN CT', st, 26000.0)
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            inputs={'ABS': 2},
        )
        # (wage/26) * (26-ABS)
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), (26000.0 / 26.0) * 24.0, places=2)

    def test_sg_mgmt_housing_expat_kpi(self):
        struct = self.structs['SG_MGMT']
        st = struct.type_id
        emp = self._create_employee('SG MGMT', st, 30000.0)
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            inputs={'EXPAT': 5},
            version_vals={'kpi_base': 12000.0, 'expat_daily': 200.0, 'housing_allowance': 5000.0},
            kpi_grade='B',
        )
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), 30000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'EXPAT_PAY'), 1000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'HOUSING'), 5000.0, places=2)
        self.assertAlmostEqual(self._line_total(slip, 'KPI_PAY'), 6000.0, places=2)

    # ---------------------------------------------------------------------
    # Tests: prorate special cases (mid-month join/leave)
    # ---------------------------------------------------------------------

    def test_prorate_mid_month_join(self):
        struct = self.structs['CN_FT']
        st = struct.type_id
        emp = self._create_employee('CN FT Join Mid', st, 30000.0)
        # join on 16th, for April 30 days => active_days = 15
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            version_vals={'date_start': date(2026, 4, 16), 'date_end': False},
        )
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), 30000.0 * (15.0 / 30.0), places=2)

    def test_prorate_mid_month_leave(self):
        struct = self.structs['CN_FT']
        st = struct.type_id
        emp = self._create_employee('CN FT Leave Mid', st, 30000.0)
        # leave on 15th, active_days = 15 for April 30 days
        slip = self._create_payslip(
            emp, struct,
            date(2026, 4, 1), date(2026, 4, 30),
            version_vals={'date_start': date(2026, 4, 1), 'date_end': date(2026, 4, 15)},
        )
        self.assertAlmostEqual(self._line_total(slip, 'BASIC'), 30000.0 * (15.0 / 30.0), places=2)

    def test_payslip_input_rejected_when_not_in_input_type_struct_ids(self):
        """input type 的 struct_ids 非空时，仅允许对应 structure 上的 payslip input。"""
        struct_cn_ft = self.structs['CN_FT']
        struct_cn_ct = self.structs['CN_CT']
        itype = self.env['hr.payslip.input.type'].create({
            'name': 'TG Structure Availability Test',
            'code': 'TGTEST_STRUCT_AVAIL',
            'struct_ids': [Command.set([struct_cn_ct.id])],
        })
        # 故意挂到 CN_FT 的 structure 上，绕开 UI domain，验证后端守门
        struct_cn_ft.write({'input_line_type_ids': [Command.link(itype.id)]})

        emp = self._create_employee('Struct Avail Test', struct_cn_ft.type_id, 10000.0)
        run = self.env['hr.payslip.run'].create({
            'name': 'TG Struct Avail Run',
            'date_start': date(2026, 4, 1),
            'date_end': date(2026, 4, 30),
            'structure_id': struct_cn_ft.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Struct Avail Slip',
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'struct_id': struct_cn_ft.id,
            'payslip_run_id': run.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        with self.assertRaises(UserError):
            self.env['hr.payslip.input'].create({
                'payslip_id': slip.id,
                'input_type_id': itype.id,
                'amount': 1.0,
                'name': itype.name,
            })

    def test_payslip_input_allowed_when_input_type_struct_ids_empty(self):
        """struct_ids 为空表示全 structure 可用。"""
        struct_cn_ft = self.structs['CN_FT']
        itype = self.env['hr.payslip.input.type'].create({
            'name': 'TG Structure Availability All',
            'code': 'TGTEST_STRUCT_ALL',
        })
        self.assertFalse(itype.struct_ids)
        struct_cn_ft.write({'input_line_type_ids': [Command.link(itype.id)]})

        emp = self._create_employee('Struct All Test', struct_cn_ft.type_id, 10000.0)
        run = self.env['hr.payslip.run'].create({
            'name': 'TG Struct All Run',
            'date_start': date(2026, 4, 1),
            'date_end': date(2026, 4, 30),
            'structure_id': struct_cn_ft.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Struct All Slip',
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'struct_id': struct_cn_ft.id,
            'payslip_run_id': run.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        line = self.env['hr.payslip.input'].create({
            'payslip_id': slip.id,
            'input_type_id': itype.id,
            'amount': 2.0,
            'name': itype.name,
        })
        self.assertTrue(line.exists())

    def test_payslip_write_struct_change_validates_existing_inputs(self):
        struct_cn_ft = self.structs['CN_FT']
        struct_cn_ct = self.structs['CN_CT']
        itype = self.env['hr.payslip.input.type'].create({
            'name': 'TG Structure Switch Test',
            'code': 'TGTEST_STRUCT_SWITCH',
            'struct_ids': [Command.set([struct_cn_ct.id])],
        })
        struct_cn_ct.write({'input_line_type_ids': [Command.link(itype.id)]})

        emp = self._create_employee('Struct Switch Emp', struct_cn_ct.type_id, 8000.0)
        run = self.env['hr.payslip.run'].create({
            'name': 'TG Struct Switch Run',
            'date_start': date(2026, 4, 1),
            'date_end': date(2026, 4, 30),
            'structure_id': struct_cn_ct.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Struct Switch Slip',
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'struct_id': struct_cn_ct.id,
            'payslip_run_id': run.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'input_line_ids': [Command.create({
                'input_type_id': itype.id,
                'amount': 1.0,
                'name': itype.name,
            })],
        })
        with self.assertRaises(UserError):
            slip.write({'struct_id': struct_cn_ft.id})

    def test_compute_sheet_blocked_when_pay_run_not_draft(self):
        """pay run 非 draft 审批态时禁止 compute_sheet（防绕过 UI）。"""
        struct = self.structs['BD_WORKER']
        emp = self._create_employee('Compute Guard Emp', struct.type_id, 10000.0)
        run = self.env['hr.payslip.run'].create({
            'name': 'TG Compute Guard Run',
            'date_start': date(2026, 4, 1),
            'date_end': date(2026, 4, 30),
            'structure_id': struct.id,
        })
        slip = self.env['hr.payslip'].create({
            'name': 'Compute Guard Slip',
            'employee_id': emp.id,
            'version_id': emp.version_id.id,
            'struct_id': struct.id,
            'payslip_run_id': run.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
        })
        run.write({'approval_state': 'approving'})
        with self.assertRaises(UserError):
            slip.compute_sheet()

