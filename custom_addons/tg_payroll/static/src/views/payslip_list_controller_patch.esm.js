/** @odoo-module **/
// 当 PayslipListController 把 PayRunCard 渲染到 list view 顶部时，
// 它通过 <Record fieldNames=...> 给 OWL Record 组件加载 hr.payslip.run。
// fieldNames 模式下 review_ids（o2m）只有 IDs，不会拉子字段（status/name/...），
// 导致 ReviewsTable 渲染空。我们 patch recordComponentProps，把 review_ids
// 的 widget 在 kanban arch 里声明的 relatedFields 注入到 activeFields.related，
// 让 Record 加载时把子字段一起拉回来。
import {patch} from "@web/core/utils/patch";
import {PayslipListController} from "@hr_payroll/views/payslip_list/hr_payslip_list_controller";

patch(PayslipListController.prototype, {
    get recordComponentProps() {
        const props = super.recordComponentProps;
        const reviewNode = Object.values(this.payRunArchInfo?.fieldNodes || {}).find(
            (f) => f.name === "review_ids"
        );
        if (!reviewNode?.views?.default?.fields) {
            return props;
        }
        const subFields = reviewNode.views.default.fields;
        const activeFields = Object.fromEntries((props.fieldNames || []).map((n) => [n, {}]));
        activeFields.review_ids = {
            related: {
                activeFields: Object.fromEntries(Object.keys(subFields).map((k) => [k, {}])),
                fields: subFields,
            },
        };
        // 同时保留 fieldNames（Record 校验需要 fieldNames+resModel 或 fields），
        // getActiveFields 会优先取 activeFields，fieldNames 只用于校验。
        return {...props, activeFields};
    },
});
