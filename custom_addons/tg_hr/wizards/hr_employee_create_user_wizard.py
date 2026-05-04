# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.mail import email_normalize


class HrEmployeeCreateUserWizard(models.TransientModel):
    _name = "tg.hr.employee.create.user.wizard"
    _description = "Create User from Employee (Onboarding Records Core)"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email / Login", required=True)
    role_ids = fields.Many2many(
        "res.users.role",
        string="Roles",
        help="Optional. When set, access groups are derived from these roles (User Roles module).",
    )
    image_1920 = fields.Binary(string="Photo", attachment=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        eid = self.env.context.get("default_employee_id")
        if not eid:
            return res
        employee = self.env["hr.employee"].browse(eid).sudo().exists()
        if not employee:
            return res
        vals = {
            "employee_id": employee.id,
            "name": employee.name or "",
            "email": employee.work_email or "",
            "image_1920": employee.image_1920,
        }
        for k, v in vals.items():
            if k in fields_list:
                res[k] = v
        return res

    def action_confirm_create_user(self):
        self.ensure_one()
        if not self.env.user.has_group("tg_hr.group_tg_hr_employee_create_user_wizard"):
            raise UserError(_("You are not allowed to create users for employees."))

        employee = self.employee_id.sudo()
        if not employee:
            raise UserError(_("Employee record is missing."))
        if employee.user_id:
            raise UserError(_("This employee already has a user."))

        normalized = email_normalize(self.email.strip()) if self.email else False
        if not normalized:
            raise UserError(_("Please enter a valid email address (used as login)."))

        Users = self.env["res.users"].sudo()
        conflicting = Users.search(
            [
                "|",
                ("email_normalized", "=", normalized),
                ("login", "=", normalized),
            ],
            limit=1,
        )
        if conflicting:
            raise UserError(_("A user already exists with this email or login."))

        partner = employee.work_contact_id
        if partner:
            partner = partner.sudo()
            if normalized and partner.email != normalized:
                partner.write({"email": normalized})
        else:
            partner = self.env["res.partner"].sudo().create(
                {
                    "name": self.name,
                    "email": normalized,
                }
            )

        company = employee.company_id or self.env.company
        vals = {
            "name": self.name,
            "login": normalized,
            "create_employee_id": employee.id,
            "partner_id": partner.id,
            "phone": employee.work_phone or False,
            "company_id": company.id,
            "company_ids": [(6, 0, [company.id])],
        }
        if self.image_1920:
            vals["image_1920"] = self.image_1920
        if self.role_ids:
            vals["role_line_ids"] = [(0, 0, {"role_id": role.id}) for role in self.role_ids]

        Users.create(vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("User created"),
                "message": _("The employee now has a linked user account."),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
