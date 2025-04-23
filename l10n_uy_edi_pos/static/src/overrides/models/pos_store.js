/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    //@override
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.cities = loadedData['res.city'];
        this.uy_doc_types = [['2','RUT'],['3','C.I.'],['4','Otros'],['5','Pasaporte'],['6','DNI']];
    },
//    push_single_order(order){
//        res = super.push_single_order(...arguments);
//        var order = this.get_order();
//        order.uy_order_server_id = res[0].id
//        return res;
//    },
});
