from odoo import fields, models, api


class UyPaymentReceipt(models.Model):
    _name = 'uy.payment.receipt'
    _description = 'Uy Payment Receipt'

    amount = fields.Float(string='Amount',)
    date = fields.Date(string='Date', related='payment_id.date', store=True)
    move_id = fields.Many2one('account.move', string='Invoice')
    payment_id = fields.Many2one('account.payment', string='Payment')


    # @api.depends('move_id.amount_residual_signed', 'payment_id.currency_id', 'payment_id.date')
    # def _compute_uy_payment_receipt_amount(self):
    #     for line in self:
    #         if line.move_id:
    #             if line.payment_id.currency_id == line.move_id.company_id.currency_id:
    #                 line.amount = abs(line.move_id.amount_residual_signed)
    #             else:
    #                 line.amount = line.move_id.currency_id._convert(abs(line.move_id.amount_residual_signed), line.payment_id.currency_id, date=line.payment_id.date)
    #         else:
    #             line.amount = 0