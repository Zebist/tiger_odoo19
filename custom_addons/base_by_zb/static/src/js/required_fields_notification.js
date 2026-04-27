import { patch } from "@web/core/utils/patch";
import { Record } from "@web/model/relational_model/record";
import { _t } from "@web/core/l10n/translation";

patch(Record.prototype, {
    _displayInvalidFieldNotification() {
        const labels = [...this._unsetRequiredFields]
            .map((f) => this.fields[f]?.string || f)
            .join(", ");
        const message = labels
            ? _t("Missing required fields: %s", labels)
            : _t("Missing required fields");
        return this.model.notification.add(message, { type: "danger" });
    },
});
