/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useEffect, useRef, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * 当 show_interview_process_page 字段值由 false 变为 true 时，
 * 自动激活 Interview Process 标签页。
 */
class InterviewProcessPageFocusField extends Component {
    static template = xml`<span class="d-none" t-ref="anchor"/>`;
    static props = { ...standardFieldProps };

    setup() {
        const anchorRef = useRef("anchor");
        useEffect(
            (show) => {
                if (!show || !anchorRef.el) return;
                Promise.resolve().then(() => {
                    const form = anchorRef.el.closest(".o_form_view");
                    if (!form) return;
                    const tab = form.querySelector(
                        '.o_notebook_headers a[name="tg_hr_interview_process"]'
                    );
                    if (tab && !tab.classList.contains("active")) {
                        tab.click();
                    }
                });
            },
            () => [this.props.record.data.show_interview_process_page]
        );
    }
}

registry.category("fields").add("interview_process_page_focus", {
    component: InterviewProcessPageFocusField,
    supportedTypes: ["boolean"],
});
