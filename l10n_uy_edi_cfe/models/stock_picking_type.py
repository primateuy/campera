from odoo import fields, models, api


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    # type of transfer
    uy_edi_cfe_type = fields.Selection([
        ('1', 'Venta'),
        ('2', 'Entre establecimientos de la misma empresa'),
    ], string="CFE Type", default='1')