from odoo import fields, models, api, _
from odoo.exceptions import UserError

class UyCFEPurchaseSync(models.Model):
    _name = 'uy.cfe.purchase.sync'
    _description = 'Sync purchase invoices with CFE'

    date_start = fields.Date(string='Start Date', required=True)
    date_end = fields.Date(string='End Date', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)

    def sync_purchase_invoices(self):
        if self.company_id.country_code != 'UY':
            raise UserError(_('This feature is only available for Uruguay companies'))
        if self.date_start > self.date_end:
            raise UserError(_('The start date must be before the end date'))
        res = self.env['account.move'].action_uy_edi_purchase_invoice(date_start= self.date_start,
                                                                       date_end=self.date_end,
                                                                       company_ids=self.company_id)
        return {'type': 'ir.actions.act_window_close'}