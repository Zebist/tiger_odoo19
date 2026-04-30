/** @odoo-module **/
// 把 OCA base_tier_validation 的 reviewsTableComponent 注册到多个域：
// - kanban / list：让对应 view 的 arch XML 能用 widget="tier_validation"
// - 无前缀 'tier_validation'：让在 OWL 组件模板里直接 <Field type="'tier_validation'"/>
//   也能查到（Field setup 用 type 做查找，且无 viewType/jsClass 上下文）
import {reviewsTableComponent} from "@base_tier_validation/components/tier_review_widget/tier_review_widget.esm";
import {registry} from "@web/core/registry";

registry.category("fields").add("kanban.tier_validation", reviewsTableComponent);
registry.category("fields").add("list.tier_validation", reviewsTableComponent);
registry.category("fields").add("tier_validation", reviewsTableComponent);
