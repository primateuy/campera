# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    uy_anonymous_id = fields.Many2one('res.partner', string='Anonymous Partner')
    # uy_branch_id = fields.Many2one('res.partner', string='Branch Street')
    # uy_branch_code = fields.Char(string='Branch Code')