/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useEffect, useRef, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * 自动激活对应的 notebook 标签页：
 *  - Offered 阶段（show_onboarding_page = true）→ Onboarding Preparation
 *  - 其他非 New 阶段（show_interview_process_page = true）→ Interview Process
 */
class InterviewProcessPageFocusField extends Component {
    static template = xml`<span class="d-none" t-ref="anchor"/>`;
    static props = { ...standardFieldProps };

    setup() {
        const anchorRef = useRef("anchor");
        useEffect(
            (showInterview, showOnboarding) => {
                if (!anchorRef.el) return;
                const tabName = showOnboarding
                    ? "tg_hr_onboarding"
                    : showInterview
                    ? "tg_hr_interview_process"
                    : null;
                if (!tabName) return;
                Promise.resolve().then(() => {
                    const form = anchorRef.el.closest(".o_form_view");
                    if (!form) return;
                    const tab = form.querySelector(
                        `.o_notebook_headers a[name="${tabName}"]`
                    );
                    if (tab && !tab.classList.contains("active")) {
                        tab.click();
                    }
                });
            },
            () => [
                this.props.record.data.show_interview_process_page,
                this.props.record.data.show_onboarding_page,
            ]
        );
    }
}

registry.category("fields").add("interview_process_page_focus", {
    component: InterviewProcessPageFocusField,
    supportedTypes: ["boolean"],
});
