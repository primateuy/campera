/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PartnerDetailsEdit } from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup();
        this.intFields.push('city_id');
        const partner = this.props.partner;
        this.changes['city_id'] = partner.city_id && partner.city_id[0]  || false;
        this.changes['uy_doc_type'] = partner.uy_doc_type  || "";
    },
});


