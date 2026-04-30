# -*- coding: utf-8 -*-
from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    skip_currency_round = fields.Boolean(
        string="Skip Currency Rounding",
        default=False,
        help="""Keep the raw float amount returned by this rule, without rounding to
the payslip currency precision.

Default behaviour (unchecked):
  - The 'result' returned by this rule is rounded to currency precision
    (e.g. 5966.7499999... → 5966.75), so line.amount in Salary Computation
    is a clean cent value.
  - When quantity = 1 and rate = 100 (the typical case), line.total equals
    line.amount, so it's also clean.

What this hook does NOT cover:
  - For percentage / non-100% rules where total = amount × qty × rate / 100
    (e.g. HRA = 25% of wage), the multiplication can still produce a
    non-cent result. Such cases are intentionally left as-is here because
    they affect very few use cases in this project; if it matters for your
    rule, do the round() inside your Python code.

Only enable this checkbox for intermediate rules whose downstream consumers
need sub-cent precision (rare in payroll).""",
    )

    def _compute_rule(self, localdict):
        """Round the rule's `amount` to the payslip currency precision before
        it flows into Salary Computation.

        Why this hook (and not `_get_payslip_line_total`):
          - This rounds the value at its source (line.amount), which gives
            a consistent display in Salary Computation's Amount column.
          - When quantity == 1 and rate == 100 (the case for all current
            tg_payroll rules), line.total == line.amount, so categories
            accumulators are also clean and NET == sum(displayed lines).
          - Trade-off: percentage / quantity-based rules' line.total may
            still drift because the multiplication happens later in
            `_get_payslip_line_total`. We accept this for now — see the
            field help on skip_currency_round.

        Per-rule opt-out: tick `skip_currency_round` on the salary rule.
        """
        amount, qty, rate = super()._compute_rule(localdict)
        if self.skip_currency_round:
            return amount, qty, rate
        payslip = localdict.get('payslip')
        currency = (payslip.currency_id or payslip.company_id.currency_id) if payslip else None
        if currency:
            amount = currency.round(amount)
        return amount, qty, rate
