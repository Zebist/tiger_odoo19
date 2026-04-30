/** @odoo-module **/
// 让点击 o_payrun_reviews_row 区域不触发 kanban 卡片打开。
// 原生 KanbanRecord.onGlobalClick 用 CANCEL_GLOBAL_CLICK selectors 判断是否吃掉点击，
// 我们 patch PayrunKanbanRecord 在原生检查前先处理 reviews 行。
import {patch} from "@web/core/utils/patch";
import {PayrunKanbanRecord} from "@hr_payroll/views/payslip_run_kanban/hr_payslip_run_kanban";

patch(PayrunKanbanRecord.prototype, {
    onGlobalClick(ev, newWindow) {
        if (ev.target.closest(".o_payrun_reviews_row")) {
            return;
        }
        return super.onGlobalClick(ev, newWindow);
    },
});
