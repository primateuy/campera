# -*- coding: utf-8 -*-

from odoo import models, fields, api

class UyRetentionPerception(models.Model):
    _name = 'uy.retention.perception'
    _description = 'Uruguayan Retention Perception'

    code_id = fields.Many2one("uy.datas", "Code", required=True, domain="[('data_code', '=', 'UY.RETENTION.PERCEPTION.CODE')]")
    name = fields.Char("Name", related="code_id.name", store=True)
    code = fields.Char("Code", related="code_id.code", readonly=True)
    rate = fields.Float(
        string='Rate (%)',
        digits='Discount',
        default=0.0,
    )
    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string="Originator Payment",
        help="The payment that created this entry")
    company_id = fields.Many2one(
        related='payment_id.company_id', store=True, readonly=True, precompute=True,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        compute='_compute_currency_id', store=True, readonly=False, precompute=True,
        required=True,
    )
    base = fields.Monetary(
        string='Base',
        currency_field='currency_id',
        default=0.0,
    )
    amount = fields.Monetary(
        string='Amount',
        compute='_compute_totals', store=True,
        currency_field='currency_id',
    )

    _sql_constraints = [
        ('table_code_uniq', 'unique(code, data_code)', 'The code of the table must be unique by table code !')
    ]

    @api.depends('rate', 'base')
    def _compute_totals(self):
        for line in self:
            line.amount = line.base * line.rate / 100

    @api.depends('payment_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = line.payment_id.currency_id or line.company_id.currency_id