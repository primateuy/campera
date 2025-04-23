/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { _t } from "@web/core/l10n/translation";
import { ConnectionLostError } from "@web/core/network/rpc_service";

patch(PaymentScreen.prototype, {
    //@override
    async validateOrder(isForceValidate) {
        this.currentOrder.set_to_invoice(true);
        if (!this.currentOrder.get_partner() && this.pos.config.uy_anonymous_id){
            var new_client = this.pos.db.get_partner_by_id(this.pos.config.uy_anonymous_id[0]);
            if (new_client){
                this.currentOrder.set_partner(new_client);
            }
        }
        if (!this.currentOrder.get_partner()){
            this.popup.add(ErrorPopup, {
                title: _t('Missing Customer'),
                body: _t("You must have a client assigned"),
            });
            return;
        }
        var client = this.currentOrder.get_partner();

        if (client.uy_doc_type){
            if (!client.vat){
                this.popup.add(ErrorPopup, {
                    title: _t('Client rut number'),
                    body: _t("You must enter number rut"),
                });
                return;
            }
            if (!client.street){
                this.popup.add('ErrorPopup', {
                    title: _t('Client Address'),
                    body: _t("You must enter an address"),
                });
                return;
            }
            if (!client.city){
                this.popup.add(ErrorPopup, {
                    title: _t('Client City'),
                    body: _t("You must enter an city"),
                });
                return;
            }
            if (!client.state_id){
                this.popup.add(ErrorPopup, {
                    title: _t('Client State'),
                    body: _t("You must enter an state"),
                });
                return;
            }

        }
        var qty_error = "";
        var price_error = "";
        for (var i = 0; i < this.currentOrder.orderlines.length; i++) {
            if (this.currentOrder.orderlines[i].quantity==0.0){
                qty_error+=this.currentOrder.orderlines.models[i].get_product().display_name + "\n";
            }
            if (this.currentOrder.orderlines[i].price==0.0){
                price_error+=this.currentOrder.orderlines[i].get_product().display_name + "\n";
            }
        }
        /*this.currentOrder.orderlines.each(_.bind( function(item) {
            if (item.qty==0.0){
                qty_error+=item.get_product().name + "<br />";
            }
        }, this));  */

        if (qty_error!=""){
            this.popup.add(ErrorPopup, {
                title: _t('The product quantity must be greater than zero'),
                body: qty_error,
            });
            return;
        }
        if (price_error!=""){
            this.popup.add(ErrorPopup, {
                title: _t('The product price must be greater than zero'),
                body: qty_error,
            });
            return;
        }
        return await super.validateOrder(isForceValidate);

    },
    async _finalizeValidation() {
        if (this.currentOrder.is_paid_with_cash() || this.currentOrder.get_change()) {
            this.hardwareProxy.openCashbox();
        }

        this.currentOrder.date_order = luxon.DateTime.now();
        for (const line of this.paymentLines) {
            if (!line.amount === 0) {
                this.currentOrder.remove_paymentline(line);
            }
        }
        this.currentOrder.finalized = true;

        // 1. Save order to server.
        this.env.services.ui.block();
        const syncOrderResult = await this.pos.push_single_order(this.currentOrder);
        this.env.services.ui.unblock();

        if (syncOrderResult instanceof ConnectionLostError) {
            this.pos.showScreen(this.nextScreen);
            return;
        } else if (!syncOrderResult) {
            return;
        }
        if (syncOrderResult[0]?.account_move) {
            this.currentOrder.uy_order_server_id = syncOrderResult[0].id
        } else {
            throw {
                code: 401,
                message: "Backend Invoice",
                data: { order: this.currentOrder },
            };
        }
        /*try {
            // 2. Invoice.
            if (this.shouldDownloadInvoice() && this.currentOrder.is_to_invoice()) {
                if (syncOrderResult[0]?.account_move) {
                    await this.report.doAction("account.account_invoices", [
                        syncOrderResult[0].account_move,
                    ]);
                } else {
                    throw {
                        code: 401,
                        message: "Backend Invoice",
                        data: { order: this.currentOrder },
                    };
                }
            }
        } catch (error) {
            if (error instanceof ConnectionLostError) {
                Promise.reject(error);
                return error;
            } else {
                throw error;
            }
        }*/

        // 3. Post process.
        if (this.currentOrder.uy_order_server_id) {
            const data = await this.orm.call("pos.order", "get_uy_pdf_invoice", [this.currentOrder.uy_order_server_id]);
            /*if (data.error){
                alert(data.error);
            }*/
            if (data.invoice) {
                this.currentOrder.uy_invoice = "data:image/png;base64,"+ data.invoice.image;
                this.currentOrder.uy_height = data.invoice.height;
                this.currentOrder.uy_width = data.invoice.width;
            }

        }

        if (
            syncOrderResult &&
            syncOrderResult.length > 0 &&
            this.currentOrder.wait_for_push_order()
        ) {
            await this.postPushOrderResolve(syncOrderResult.map((res) => res.id));
        }

        await this.afterOrderValidation(!!syncOrderResult && syncOrderResult.length > 0);
    }
});
