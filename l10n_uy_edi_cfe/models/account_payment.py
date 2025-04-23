# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountPayment(models.Model):
    _inherit = "account.payment"

    uy_retention_perception_ids = fields.One2many("uy.retention.perception", "payment_id", string="Retention/Perception")
    uy_retention_perception_amount = fields.Monetary(string="Retention/Perception Amount", compute="_compute_uy_retention_perception_amount")
    # uy_is_cfe = fields.Boolean("Is CFE", compute="_cumpute_uy_is_cfe")
    # uy_is_refund = fields.Boolean("Is Refund")
    uy_is_edi_receipt = fields.Boolean("Is Receipt", related="journal_id.uy_is_edi_receipt", store=True)
    uy_document_code = fields.Selection(selection="_get_uy_invoice_code", string="Invoice Type Code", compute="_compute_uy_document_code", store=True)
    # uy_receipt_number = fields.Char("Receipt Number")
    uy_payment_receipt_ids = fields.One2many("uy.payment.receipt", "payment_id", string="Payment Receipts")
    uy_payment_receipt_total = fields.Monetary(string="Payment Receipt Total", compute="_compute_uy_payment_receipt_total")
    uy_cfe_state = fields.Char("UY EDI State", compute="_compute_uy_edi_state", copy=False)

    @api.depends("uy_cfe_id.state")
    def _compute_uy_edi_state(self):
        for payment in self:
            payment.uy_cfe_state = payment.uy_cfe_id.state

    def action_uy_sent_receipt(self):
        self.ensure_one()
        if not self.uy_is_edi_receipt:
            raise UserError(_("Only receipts can be sent"))
        if not self.is_reconciled:
            raise UserError(_("The receipt must be reconciled"))
        if self.amount_residual != 0.0:
            raise UserError(_("The receipt must have residual amount"))
        reconciled_invoice_ids = self.reconciled_invoice_ids
        if reconciled_invoice_ids.filtered(lambda s: s.uy_cfe_id.state != 'sent'):
            raise UserError(_("The invoice must be sent before it can be reconciled"))
        if reconciled_invoice_ids.filtered(lambda s: s.invoice_date >= s.invoice_date_due):
            raise UserError(_("The invoice date must be greater than the due date."))
        if self.move_id.uy_cfe_id and self.move_id.uy_cfe_id.state == 'sent':
            raise UserError(_("The receipt has already been sent"))
        self.uy_payment_receipt_ids.unlink()
        self._compute_uy_document_code()
        uy_payment_receipt_ids = []
        for invoice_id in self.reconciled_invoice_ids:
            if invoice_id.state != 'posted':
                raise UserError(_("The invoice must be posted"))
            line_ids = self.line_ids.filtered(lambda s: s.account_id.account_type in ['asset_receivable', 'liability_payable'])
            matched_debit_ids = line_ids.mapped('matched_debit_ids').filtered(lambda s: s.debit_move_id.move_id == invoice_id)
            amount_payment = 0.0
            for matched_debit_id in matched_debit_ids:
                if matched_debit_id.debit_move_id.move_id == invoice_id:
                    amount_payment += matched_debit_id.debit_amount_currency
            matched_credit_ids = line_ids.mapped('matched_credit_ids').filtered(lambda s: s.credit_move_id.move_id == invoice_id)
            for matched_credit_id in matched_credit_ids:
                if matched_credit_id.credit_move_id.move_id == invoice_id:
                    amount_payment += matched_credit_id.credit_amount_currency
            uy_payment_receipt_ids.append((0, 0, {'move_id': invoice_id.id, 'amount': amount_payment}))
        self.write({'uy_payment_receipt_ids': uy_payment_receipt_ids})
        if not self.move_id.uy_cfe_id:
            edi_format_id = self.env.ref('l10n_uy_edi_cfe.edi_uy_cfe')
            document_id = self.env['account.edi.document'].create({
                                                                    # 'name': self.name,
                                                                    'move_id': self.move_id.id,
                                                                    'state': 'to_send',
                                                                    'edi_format_id': edi_format_id.id
                                                                })
        else:
            self.move_id.uy_cfe_id.blocking_level = False
        # document_id.action_send_document()
        # edi_format_id._check_move_configuration(self.move_id)
        # document_vals  = edi_format_id._uy_post_cfe(self.move_id)
        # document_id.write(document_vals)
        self.move_id.action_process_edi_web_services()
        return True

    @api.depends("uy_payment_receipt_ids.amount", "uy_is_edi_receipt")
    def _compute_uy_payment_receipt_total(self):
        for payment in self:
            payment.uy_payment_receipt_total = sum(payment.uy_payment_receipt_ids.mapped('amount'))

    @api.model
    def _get_uy_invoice_code(self):
        return self.env['uy.datas'].get_by_code("UY.DOCUMENT.CODE")

    @api.depends("journal_id", "journal_id.uy_is_edi_receipt")
    def _compute_uy_document_code(self):
        for payment in self:
            if payment.journal_id.uy_is_edi_receipt:
                payment.uy_document_code = payment.reconciled_invoice_ids and payment.reconciled_invoice_ids[0].uy_document_code or False
            else:
                payment.uy_document_code = payment.journal_id.uy_document_code

    def action_uy_refund(self):
        payment_ids = self.env['account.payment']
        payment_type = False
        for payment_id in self:
            if not payment_id.uy_is_cfe and not payment_id.state == 'posted':
                raise UserError(_("Only CFE payments can be refunded"))
            if payment_id.reversed_entry_id:
                raise UserError(_("This payment has already been refunded"))
            vals = {}
            if payment_id.payment_type == 'inbound' and not payment_type:
                payment_type = 'inbound'
            vals['reversed_entry_id'] = payment_id.move_id.id
            if payment_id.payment_type == 'inbound':
                vals['payment_type'] = 'outbound'
            else:
                vals['payment_type'] = 'inbound'
            vals['ref']= payment_id.name
            payment_new_id = payment_id.copy()
            for retention_perception in payment_id.uy_retention_perception_ids:
                retention_perception.copy(default={'payment_id': payment_new_id.id})
            # payment_new_id._compute_outstanding_account_id()
            # payment_new_id._compute_destination_account_id()
            payment_new_id.write(vals)
            payment_ids |= payment_new_id
        action = self.env['ir.actions.actions']._for_xml_id('account.action_account_payments')
        if len(payment_ids) > 1:
            action['domain'] = [('id', 'in', payment_ids.ids)]
        elif len(payment_ids) == 1:
            form_view = [(self.env.ref('account.view_account_payment_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = payment_ids.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        if payment_type:
            context = {'default_payment_type': 'inbound',
                       'default_partner_type': 'customer',
                       'search_default_inbound_filter': 1,
                       'default_move_journal_types': ('bank', 'cash'), }
        else:
            context = {'default_payment_type': 'outbound',
                       'default_partner_type': 'supplier',
                       'search_default_outbound_filter': 1,
                       'default_move_journal_types': ('bank', 'cash'),}
        if len(self) == 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_ref': self.name,
            })
        action['context'] = context
        return action

    @api.depends('uy_retention_perception_ids', 'uy_retention_perception_ids.amount')
    def _compute_uy_retention_perception_amount(self):
        for record in self:
            record.uy_retention_perception_amount = sum(record.uy_retention_perception_ids.mapped('amount'))

    def action_post(self):
        for payment in self:
            if payment.uy_is_cfe and not payment.uy_is_edi_receipt:
                if payment.uy_is_cfe and not payment.uy_retention_perception_ids:
                    raise UserError(_("CFE must have Retention/Perception"))
                if payment.uy_retention_perception_ids and payment.uy_document_code == '182' and payment.uy_is_cfe \
                        and round(payment.uy_retention_perception_amount,2) != round(payment.amount,2):
                    payment.amount = payment.uy_retention_perception_amount
            elif payment.uy_is_cfe and not payment.uy_is_edi_receipt:
                if payment.uy_is_cfe and not payment.uy_retention_perception_ids:
                    raise UserError(_("CFE must have Retention/Perception"))
                if payment.uy_retention_perception_ids and payment.uy_document_code == '182' and payment.uy_is_cfe \
                        and round(payment.uy_retention_perception_amount,2) != round(payment.amount,2):
                    payment.amount = payment.uy_retention_perception_amount
        res = super(AccountPayment, self).action_post()
        return res

    def _synchronize_to_moves(self, changed_fields):
        res = super(AccountPayment, self)._synchronize_to_moves(changed_fields)
        for pay in self.with_context(skip_account_move_synchronization=True):
            pay.move_id\
                .with_context(skip_invoice_sync=True)\
                .write({
                    'uy_document_code': pay.journal_id.uy_document_code
                })
        return res

    # @api.depends("journal_id")
    # def _cumpute_uy_is_cfe(self):
    #     for payment in self:
    #         payment.uy_is_cfe = bool(payment.journal_id.edi_format_ids.filtered(lambda j: j.code == 'edi_uy_cfe'))

    def action_draft(self):
        for payment in self:
            if payment.uy_cfe_state =='sent' and (payment.uy_is_cfe or payment.uy_is_edi_receipt ):
                raise UserError(_("The CFE can convert us to a draft because it has a submission to the DGI"))
        res = super(AccountPayment, self).action_draft()
        return res