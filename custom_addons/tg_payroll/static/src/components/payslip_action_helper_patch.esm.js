/** @odoo-module **/
// PayslipActionHelper 是 slip list 的空态占位。原生在 payrun 上下文里固定显示
// "Generate Payslips"，这里把它收紧到 run.approval_state === 'draft' 才显示，
// 跟 kanban 卡 gen_payslip slot 行为对齐。
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl";
import { PayslipActionHelper } from "@hr_payroll/components/payslip_action_helper/payslip_action_helper";

patch(PayslipActionHelper.prototype, {
    setup() {
        super.setup?.();
        this.orm = useService("orm");
        this.runState = useState({ approvalState: null });
        onWillStart(async () => {
            if (!this.props.payrunId) {
                return;
            }
            const [rec] = await this.orm.read(
                "hr.payslip.run",
                [this.props.payrunId],
                ["approval_state"],
            );
            this.runState.approvalState = rec?.approval_state;
        });
    },
});
