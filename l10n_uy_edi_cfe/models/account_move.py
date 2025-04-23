# -*- encoding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from num2words import num2words
from io import BytesIO
from base64 import decodebytes, encodebytes
import uuid
from datetime import timedelta
import logging
import re
_logger = logging.getLogger(__name__)
try:
    import qrcode

    qr_mod = True
except:
    qr_mod = False
import json

class AccountMove(models.Model):
    _inherit = "account.move"

    uy_currency_rate = fields.Float("Currency Rate", store=True, readonly=True,
                                       compute='_compute_uy_currency_rate', copy=False, digits=(12, 3))
    uy_tax_min_rate = fields.Float("Tax Minimun Rate", compute='_get_uy_amount_total', store=True, copy=False)
    uy_tax_basic_rate = fields.Float("Tax Basic Rate", compute='_get_uy_amount_total', store=True, copy=False)

    uy_amount_unafected = fields.Float("Unafected", compute='_get_uy_amount_total', store=True, copy=False)
    uy_tax_min_base = fields.Float("Tax Minimun Base", compute='_get_uy_amount_total', store=True, copy=False)
    uy_tax_basic_base = fields.Float("Tax Basic Base", compute='_get_uy_amount_total', store=True, copy=False)
    uy_tax_min = fields.Float("Tax Minimun Amount", compute='_get_uy_amount_total', store=True, copy=False)
    uy_tax_basic = fields.Float("Tax Basic Amount", compute='_get_uy_amount_total', store=True, copy=False)
    uy_amount_untaxed = fields.Float("Amount Untaxed Amount", compute='_get_uy_amount_total', store=True, copy=False)

    uy_document_code = fields.Selection(selection="_get_uy_invoice_code", string="Invoice Type Code")

    uy_cfe_serie = fields.Char("Serie", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_cfe_number = fields.Char("CFE Number", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_qr_id = fields.Many2one('ir.attachment', "Qr Code", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_security_code = fields.Char("Security Code", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_constancy = fields.Char("Constancy", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_constancy_serie = fields.Char("Constancy Serie", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_constancy_from = fields.Char("Constancy From", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_constancy_to = fields.Char("Constancy To", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_constancy_vto = fields.Char("Constancy Vto", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_url_code = fields.Char("Url Code", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_attachment_id = fields.Many2one('ir.attachment', "Document", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_cfe_id = fields.Many2one('account.edi.document', "UY EDI", compute="_compute_uy_edi_detail", store=True,
                                       copy=False)
    uy_res_cfe_id = fields.Char("EDI Response ID", store=True, copy=False)

    uy_qr_code = fields.Binary("Qr Code Data", compute="_compute_uy_qr_code", copy=False)
    uy_gross_amount = fields.Selection([('0', 'Untaxed'),
                                        ('1', 'Taxes included'),
                                        ('2', 'Untaxed e-Boleta')], "Gross Amount", compute='_compute_uy_gross_amount', copy=False)

    uy_reversed_entry_id = fields.Many2one('account.move', string="Reversal of Credit/Debit Note",
                                           compute="_cumpute_uy_reversed_entry_id",
                                           inverse="_inverse_uy_reversed_entry_id")
    uy_is_cfe = fields.Boolean("Is CFE", compute="_cumpute_uy_is_cfe")

    uy_clause = fields.Selection(selection="_get_uy_clause", string="Sales Clause")
    uy_transport = fields.Selection(selection="_get_uy_transport", string="Transport")
    uy_sales_mode = fields.Selection(selection="_get_uy_sales_mode", string="sales Mode")
    uy_print = fields.Boolean("Print PDF")
    uy_uuid = fields.Char("Uuid Uruguayan", copy=False, default=lambda s: str(uuid.uuid4()))
    @api.onchange('uy_document_code')
    def _onchange_uy_document_code(self):
        document_type_obj = self.env['l10n_latam.document.type']
        for move in self:
            l10n_latam_document_type_id = document_type_obj.search([('code','=',move.uy_document_code)], limit=1)
            if l10n_latam_document_type_id:
                move.l10n_latam_document_type_id = l10n_latam_document_type_id
            else:
                move.l10n_latam_document_type_id = self.env.ref('l10n_uy.dc_inv')


    @api.model
    def action_check_cfe_pdf_from_moves(self, days=15, limit=20, sale=False):
        date = fields.Date.today() - timedelta(days=days)
        domain = [('date', '>=', date), ('state', '=', 'posted'),
                  ('company_id.uy_server','in',['biller']), ('uy_is_cfe', '=', False)]
        if not sale:
            domain += [('move_type', 'in', ['out_invoice', 'out_refund', 'entry'])]

        move_ids = self.search(domain, limit=limit, order='date ASC')
        move_ids.action_check_cfe_pdf_status()

    def action_retry_edi_documents_error(self):
        res = super(AccountMove, self.with_context(uy_check_cfe=True)).action_retry_edi_documents_error()
        return res
    
    def action_check_cfe_pdf_status(self):
        for move in self:
            edi_document_ids = move.edi_document_ids.filtered(
                lambda s: s.edi_format_id.code == 'edi_uy_cfe' and s.state == 'sent')
            edi_document_id = len(edi_document_ids) > 1 and edi_document_ids[0] or edi_document_ids
            if edi_document_id or move.move_type in ['in_invoice', 'in_refund', 'entry']:
                if not move.uy_print and (move.uy_cfe_id or move.move_type in ['in_invoice', 'in_refund', 'entry']):
                    if not move.uy_res_cfe_id and move.company_id.uy_server == 'biller' and move.move_type in ['in_invoice', 'in_refund', 'entry']:
                        # No se puede obtener el pdf de la factura
                        raise UserError(_("Can't get the pdf of the invoice"))
                    if move.company_id.uy_server == 'efactura' and move.move_type in ['in_invoice', 'in_refund', 'entry'] and not re.findall(r'^.*([A-Z]{1,2})(\d{1,7})$', move.name or ''):
                        # No se puede obtener el pdf de la factura
                        raise UserError(_("Can't get the pdf of the invoice"))
                    res = self.env['uy.edi.send.cfe'].get_cfe_pdf(move, edi_document_id)
                    if res.get('estado') and res.get('respuesta', {}).get('pdf', ''):
                        data = res.get('respuesta', {})
                        if data.get('pdf') and not edi_document_id.attachment_id:
                            attachment_id = self.env['ir.attachment'].create({
                                'name': "%s.pdf" % (move.name),
                                'datas': data.get('pdf').encode('utf-8'),
                                'mimetype': 'application/pdf'
                            })
                            edi_document_id.attachment_id = attachment_id.id
                        move.uy_print = True

                        move.message_post(body=_('The electronic document succeeded.'),
                                          attachments=[("%s.pdf" % (move.name),
                                                        decodebytes(data.get('pdf', '').encode('utf-8')))])

                    else:
                        move.message_post(body=_('Error. %s') % res.get('respuesta', {}))

                if not move.uy_constancy and move.move_type not in ['in_invoice', 'in_refund', 'entry']:
                    res = self.env['uy.edi.send.cfe'].get_cfe_invoice_status(move, edi_document_id)
                    if res.get('estado') and res.get('respuesta', {}).get('cae', ''):
                        data = res.get('respuesta', {})
                        if data.get('cae'):
                            vals = {
                                'uy_constancy': data.get('cae', {}).get('numero', False),
                                'uy_constancy_serie': data.get('cae', {}).get('serie', False),
                                'uy_constancy_from': data.get('cae', {}).get('inicio') and str(
                                    data.get('cae', {}).get('inicio')) or False,
                                'uy_constancy_to': data.get('cae', {}).get('fin') and str(
                                    data.get('cae', {}).get('fin')) or False,
                                'uy_constancy_vto': data.get('cae', {}).get('fecha_expiracion', False)
                            }
                            edi_document_id.write(vals)

                        move.message_post(body=_('CAE the electronic document succeeded.<br/>'))

                    else:
                        move.message_post(body=_('Error.<br/> %s') % res.get('respuesta', {}))

    @api.model
    def _get_uy_sales_mode(self):
        return self.env['uy.datas'].get_by_code("UY.SALES.MODE")

    @api.model
    def _get_uy_transport(self):
        return self.env['uy.datas'].get_by_code("UY.TRANSPORT")

    @api.model
    def _get_uy_clause(self):
        return self.env['uy.datas'].get_by_code("UY.CLAUSE")

    @api.depends("journal_id")
    def _cumpute_uy_is_cfe(self):
        for move in self:
            move.uy_is_cfe = bool(move.journal_id.edi_format_ids.filtered(lambda j: j.code == 'edi_uy_cfe'))

    @api.depends('debit_origin_id', 'reversed_entry_id')
    def _cumpute_uy_reversed_entry_id(self):
        for move in self:
            if move.is_sale_document():
                if move.uy_document_code in ['102', '112']:
                    move.uy_reversed_entry_id = move.reversed_entry_id.id
                elif move.uy_document_code in ['103', '113']:
                    move.uy_reversed_entry_id = move.debit_origin_id.id
                else:
                    move.uy_reversed_entry_id = False
            else:
                move.uy_reversed_entry_id = False

    def _inverse_uy_reversed_entry_id(self):
        for move in self:
            if move.is_sale_document():
                if move.uy_document_code in ['102', '112', '122']:
                    move.reversed_entry_id = move.uy_reversed_entry_id.id
                elif move.uy_document_code in ['103', '113', '123']:
                    move.debit_origin_id = move.uy_reversed_entry_id.id

    @api.depends('invoice_line_ids', 'invoice_line_ids.tax_ids')
    def _compute_uy_gross_amount(self):
        for move in self:
            tax_ids = move.invoice_line_ids.mapped('tax_ids').filtered(lambda s: s.amount > 0.0)
            if move.uy_document_code not in ['151', '152', '153']:
                if tax_ids and len(tax_ids) == len(tax_ids.filtered(lambda s: s.price_include == True)):
                    move.uy_gross_amount = '1'
                elif tax_ids and len(tax_ids) == len(tax_ids.filtered(lambda s: s.price_include == False)):
                    move.uy_gross_amount = '0'
                else:
                    move.uy_gross_amount = '0'
            else:
                move.uy_gross_amount = '2'

    def uy_recompute_dynamic_lines(self):
        for invoice_id in self:
            invoice_id._onchange_currency()
            invoice_id._recompute_dynamic_lines(recompute_all_taxes=True)
        return True

    @api.depends('edi_document_ids.uy_cfe_serie',
                 'edi_document_ids.uy_cfe_number',
                 'edi_document_ids.uy_qr_id',
                 'edi_document_ids.uy_security_code',
                 'edi_document_ids.uy_constancy',
                 'edi_document_ids.uy_constancy_serie',
                 'edi_document_ids.uy_constancy_from',
                 'edi_document_ids.uy_constancy_to',
                 'edi_document_ids.uy_constancy_vto',
                 'edi_document_ids.uy_url_code',
                 'edi_document_ids.attachment_id',
                 'edi_document_ids.uy_cfe_id')
    def _compute_uy_edi_detail(self):
        for move in self:
            edi_document_ids = move.edi_document_ids.filtered(lambda s: s.edi_format_id.code == 'edi_uy_cfe')
            edi_document_id = len(edi_document_ids) > 1 and edi_document_ids[0] or edi_document_ids
            uy_cfe_serie = move.edi_document_ids.filtered(lambda s: s.edi_format_id.code == 'edi_uy_cfe')
            move.uy_cfe_serie = edi_document_id.uy_cfe_serie
            move.uy_cfe_number = edi_document_id.uy_cfe_number
            move.uy_qr_id = edi_document_id.uy_qr_id
            move.uy_security_code = edi_document_id.uy_security_code
            move.uy_constancy = edi_document_id.uy_constancy
            move.uy_constancy_serie = edi_document_id.uy_constancy_serie
            move.uy_constancy_from = edi_document_id.uy_constancy_from
            move.uy_constancy_to = edi_document_id.uy_constancy_to
            move.uy_constancy_vto = edi_document_id.uy_constancy_vto
            move.uy_url_code = edi_document_id.uy_url_code
            move.uy_attachment_id = edi_document_id.attachment_id
            move.uy_cfe_id = edi_document_id.id
            # move.uy_res_cfe_id = edi_document_id.uy_cfe_id

    @api.depends('uy_qr_id', 'uy_url_code')
    def _compute_uy_qr_code(self):
        for move in self:
            move.uy_qr_code = False
            if not move.uy_is_cfe:
                move.uy_qr_code = False
            elif move.uy_qr_id or move.uy_url_code:
                if move.uy_qr_id:
                    move.uy_qr_code = move.uy_qr_id.datas
                elif move.uy_url_code and qr_mod:
                    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_Q)
                    qr.add_data(move.uy_url_code or ' ')
                    qr.make(fit=True)
                    image = qr.make_image()
                    tmpf = BytesIO()
                    image.save(tmpf, 'png')
                    move.uy_qr_code = encodebytes(tmpf.getvalue())
                else:
                    move.uy_qr_id = False
            else:
                move.uy_qr_id = False

    @api.model
    def _get_uy_invoice_code(self):
        return self.env['uy.datas'].get_by_code("UY.DOCUMENT.CODE")

    @api.depends('date', 'currency_id', 'invoice_date')
    def _compute_uy_currency_rate(self):
        to_currency = self.env.ref('base.UYU')
        for move in self:
            rate = self.env['res.currency']._get_conversion_rate(move.currency_id, to_currency, move.company_id,
                                                                 move.invoice_date or move.date)
            move.uy_currency_rate = rate

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        journal_id = self.journal_id
        if self.partner_id.uy_doc_type == '2' and self.move_type in ['out_invoice', 'in_invoice']:
            self.uy_document_code = '111'
        elif self.partner_id.uy_doc_type != '2' and self.move_type in ['out_invoice', 'in_invoice']:
            self.uy_document_code = '101'
        if self.partner_id.uy_doc_type == '2' and self.move_type in ['out_refund', 'in_refund']:
            self.uy_document_code = '112'
        elif self.partner_id.uy_doc_type != '2' and self.move_type in ['out_refund', 'in_refund']:
            self.uy_document_code = '102'
        if journal_id.uy_document_code != self.uy_document_code:
            journal_id = self.env['account.journal'].search(
                [('uy_document_code', '=', self.uy_document_code), ('type', '=', journal_id.type),
                 ('company_id', '=', self.company_id.id)], limit=1)
            if journal_id:
                self.journal_id = journal_id.id
        return res

    def _check_update_uy_sequence(self):
        for move in self.filtered(lambda s: s.edi_document_ids):
            if not move.payment_id.uy_is_edi_receipt:
                if move.uy_cfe_serie and move.uy_cfe_number and move.name != "%s-%s" % (
                move.uy_cfe_serie, move.uy_cfe_number):
                    # before_state = move.state
                    # move.with_context(tracking_disable=True).state = 'draft'
                    move.name = move._get_uy_name_by_serie_number()
                    move.payment_reference = move.name
                    # move.with_context(tracking_disable=True).state = before_state
                if move.edi_document_ids.filtered(lambda d: d.state in ('cancelled')):
                    before_name = move.name
                    # before_state = move.state
                    # move.with_context(tracking_disable=True).state = 'draft'
                    annul = _("ANNUL")
                    if not annul in before_name:
                        move.name = _("%s/%s") % (annul, before_name)
                    # move.with_context(tracking_disable=True).state = before_state

    def _get_uy_name_by_serie_number(self):
        self.ensure_one()
        if self.uy_cfe_serie and self.uy_cfe_number:
            return "%s-%s" % (self.uy_cfe_serie, self.uy_cfe_number)
        else:
            return self.name

    def _post(self, soft=True):
        res = super(AccountMove, self)._post(soft=soft)
        for move in self:
            if move.uy_is_cfe and move.company_id.uy_sync_mode:
                move.action_process_edi_web_services()
        return res

    @api.depends('line_ids.price_subtotal', 'line_ids.tax_base_amount', 'line_ids.tax_line_id', 'partner_id',
                 'currency_id')
    def _get_uy_amount_total(self):

        for move in self:
            uy_tax_basic_rate = self.env['account.tax'].search([('company_id', '=', move.company_id.id),
                                                                ('type_tax_use', '=', 'sale'),
                                                                ('uy_tax_type', '=', '22')], limit=1).amount
            uy_tax_min_rate = self.env['account.tax'].search([('company_id', '=', move.company_id.id),
                                                              ('type_tax_use', '=', 'sale'),
                                                              ('uy_tax_type', '=', '10')], limit=1).amount
            move.uy_tax_min_rate = uy_tax_min_rate or 0.0
            move.uy_tax_basic_rate = uy_tax_basic_rate or 0.0

            tax_lines = move.line_ids.filtered(lambda line: line.tax_line_id)
            tax_balance_multiplicator = -1 if move.is_inbound(True) else 1
            res = {}
            done_taxes = set()
            for line in tax_lines:
                res.setdefault(line.tax_line_id.uy_tax_type, {'base': 0.0, 'amount': 0.0})
                res[line.tax_line_id.uy_tax_type]['amount'] += tax_balance_multiplicator * (
                    line.amount_currency if line.currency_id else line.balance)
                #tax_key_add_base = ('tax_repartition_line_id', 'group_tax_id', 'account_id', 'currency_id', 'analytic_tag_ids', 'analytic_account_id', 'tax_ids', 'tax_tag_ids', 'partner_id')
                #if tax_key_add_base not in done_taxes:
                if line.currency_id and line.company_currency_id and line.currency_id != line.company_currency_id:
                    amount = line.company_currency_id._convert(line.tax_base_amount, line.currency_id,
                                                               line.company_id,
                                                               line.date or fields.Date.context_today(self))
                else:
                    amount = line.tax_base_amount
                res[line.tax_line_id.uy_tax_type]['base'] += amount
                # The base should be added ONCE
                # done_taxes.add(tax_key_add_base)

            # At this point we only want to keep the taxes with a zero amount since they do not
            # generate a tax line.
            zero_taxes = set()
            for line in move.line_ids:
                for tax in line.tax_ids.flatten_taxes_hierarchy():
                    if tax.uy_tax_type not in res or tax.uy_tax_type in zero_taxes:
                        res.setdefault(tax.uy_tax_type, {'base': 0.0, 'amount': 0.0})
                        res[tax.uy_tax_type]['base'] += tax_balance_multiplicator * (
                            line.amount_currency if line.currency_id else line.balance)
                        zero_taxes.add(tax.uy_tax_type)



            move.uy_amount_untaxed = res.get('0', {}).get('base', 0.0)
            move.uy_amount_unafected = res.get('0', {}).get('amount', 0.0)

            move.uy_tax_min_base = res.get('10', {}).get('base', 0.0)
            move.uy_tax_basic_base = res.get('22', {}).get('base', 0.0)

            move.uy_tax_min = res.get('10', {}).get('amount', 0.0)
            move.uy_tax_basic = res.get('22', {}).get('amount', 0.0)

    def action_process_edi_web_services(self, with_commit=True):
        res = super(AccountMove, self).action_process_edi_web_services(with_commit)
        # if self.env.context.get('uy_check_cfe'):
        #     docs = self.edi_document_ids.filtered(
        #         lambda d: d.state in ('to_send', 'to_cancel'))
        #     docs._process_documents_web_services(with_commit=with_commit)
        self._check_update_uy_sequence()
        return res

    def button_cancel_posted_moves(self):
        acepted_documents = self.mapped('edi_document_ids').filtered(lambda s: s.state == 'sent')
        if acepted_documents:
            raise ValidationError(_("The document cannot be canceled, you must issue a credit note"))
        res = super(AccountMove, self).button_cancel_posted_moves()

    def uy_import_message_post(self, pdf_file):
        self.ensure_one()
        self.message_post(body=_('Sending the electronic document succeeded.<br/>'),
                          attachments=[("%s.pdf" % self.name,
                                        decodebytes(pdf_file.encode('utf-8')))])
        return True

    def action_invoice_sent(self):
        res = super(AccountMove, self).action_invoice_sent()
        context = dict(res.get('context'))
        if self.uy_is_cfe and self.uy_attachment_id:
            attachment_ids = []
            if self.uy_attachment_id and self.journal_id.uy_efactura_print_mode:
                attach_id = self.uy_attachment_id.copy()
                attach_id.write({'res_model': 'mail.compose.message', 'res_id': '0'})
                attachment_ids.append(attach_id.id)
            context['default_attachment_ids'] = [(6, 0, attachment_ids)]
            res['context'] = context
        return res

    def action_invoice_sent(self):
        res = super(AccountMove, self).action_invoice_sent()
        context = dict(res.get('context'))
        if self.uy_is_cfe and self.uy_attachment_id:
            attachment_ids = []
            if self.uy_attachment_id:
                attach_id = self.uy_attachment_id.copy()
                attach_id.write({'res_model': 'mail.compose.message', 'res_id': '0'})
                attachment_ids.append(attach_id.id)
            context['default_attachment_ids'] = [(6, 0, attachment_ids)]
            res['context'] = context
        return res

    def action_uy_invoice_print(self):
        self.ensure_one()
        if self.uy_is_cfe and self.uy_attachment_id:
            res = {
                'type': 'ir.actions.act_url',
                'url': '/web/content/ir.attachment/%d/datas/%s' % (
                self.uy_attachment_id.id, self.uy_attachment_id.name),
                'target': 'new',
            }
        else:
            res = self.action_invoice_print()
            res.update({'close_on_report_download': True})
        self.filtered(lambda inv: not inv.is_move_sent).write({'is_move_sent': True})
        return res

    def _uy_purchase_invoice_by_efactura(self, invoice, company_id):
        other = self.env.ref('l10n_uy.it_other')
        rut = self.env.ref('l10n_uy.it_rut')
        tipo = str(invoice.get('tipo'))
        serie = invoice.get('serie')
        num = int(invoice.get('numero'))
        vat = invoice.get('rut_emisor')
        moneda = invoice.get('moneda')
        bruto = float(invoice.get('total_neto'))
        iva = float(invoice.get('total_iva'))
        l10n_latam_document_type_id = self.env['l10n_latam.document.type'].search(
            [('code', '=', tipo), ('country_id', '=', company_id.country_id.id)], limit=1)
        if tipo in ['181']:
            return {}
        if l10n_latam_document_type_id.doc_code_prefix and tipo not in ['182']:
            name = "%s %s%07d" % (str(l10n_latam_document_type_id.doc_code_prefix), serie, num)
        else:
            name = "%s%07d" % (serie, num)
        currency_id = self.env['res.currency'].search([('name', '=', moneda)], limit=1)
        if not currency_id:
            currency_id = self.env['res.currency'].search([('name', '=', 'UYU')], limit=1)

        if tipo not in ['182']:
            invoice_id = self.search([('name', '=', name), ('partner_id.vat', '=', vat)])
            if not invoice_id:
                partner_id = self.env['res.partner'].search([('vat', '=', vat)], limit=1)
                if not partner_id:
                    try:
                        partner_id = self.env['res.partner'].create(
                            {'name': vat, 'l10n_latam_identification_type_id': rut.id, 'vat': vat,
                             'country_id': self.env.ref('base.uy').id})
                    except Exception as e:
                        partner_id = self.env['res.partner'].create(
                            {'name': vat, 'l10n_latam_identification_type_id': other.id, 'vat': vat,
                             'country_id': self.env.ref('base.uy').id})
                move_type = tipo in ['101', '103', '111', '113', '121', '123', '151',
                                     '153'] and 'in_invoice' or 'in_refund'
                tax_amount = float(int(round((iva / (bruto or 1)) * 100)))
                tax_id = self.env['account.tax'].search(
                    [('company_id', '=', company_id.id), ('amount', '=', tax_amount), ('type_tax_use', '=', 'purchase'),
                     ('price_include', '=', False)], limit=1)
                fecha_vencimiento = invoice.get('fecha_vencimiento') or ''
                if fecha_vencimiento == '0000-00-00':
                    fecha_vencimiento = invoice.get('fecha', False)
                else:
                    fecha_vencimiento = invoice.get('fecha_vencimiento', False)
                vals = {
                        'name': name,
                        'partner_id': partner_id.id,
                        'move_type': move_type,
                        'currency_id': currency_id.id,
                        'invoice_date': invoice.get('fecha', False),
                        'date': invoice.get('fecha', False),
                        'invoice_date_due': fecha_vencimiento or invoice.get('fecha', False),
                        'uy_document_code': tipo,
                        'uy_cfe_serie': serie,
                        'uy_cfe_number': num,
                    }
                vals['invoice_line_ids'] = [
                    (0, 0, {
                        'name': name,
                        'quantity': 1,
                        'price_unit': tax_id and bruto or (bruto + iva),
                        'tax_ids': tax_id and tax_id.ids or []
                    })
                ]
                if l10n_latam_document_type_id:
                    vals['l10n_latam_document_type_id'] = l10n_latam_document_type_id.id
                if not tax_id:
                    _logger.info(json.dumps(invoice, indent=4))
                new_invoice_id = self.create(vals)
                new_invoice_id.message_post(body=json.dumps(invoice, indent=4))
        else:
            payment_id = self.env['account.payment'].search([('ref', '=', name), ('partner_id.vat', '=', vat)])
            if not payment_id:
                partner_id = self.env['res.partner'].search([('vat', '=', vat)], limit=1)
                if not partner_id:
                    try:
                        partner_id = self.env['res.partner'].create(
                            {'name': vat, 'l10n_latam_identification_type_id': rut.id, 'vat': vat,
                             'country_id': self.env.ref('base.uy').id})
                    except Exception as e:
                        partner_id = self.env['res.partner'].create(
                            {'name': vat, 'l10n_latam_identification_type_id': other.id, 'vat': vat})
                vals = {}
                vals['payment_type'] = 'inbound'
                vals['currency_id'] = currency_id.id
                vals['partner_id'] = partner_id.id
                vals['amount'] = bruto
                vals['ref'] = name
                vals['uy_cfe_serie'] = serie
                vals['uy_cfe_number'] = num
                # vals['communication'] = name
                vals['date'] = invoice.get('fecha', False)
                try:
                    new_payment_id = self.env['account.payment'].create(vals)
                    new_payment_id.message_post(body=json.dumps(invoice, indent=4))
                except Exception as e:
                    _logger.info(e)

    def _uy_purchase_invoice_by_biller(self, invoice, company_id):
        if str(invoice.get('tipo_comprobante', '')) in ['181']:
            return {}
        other = self.env.ref('l10n_uy.it_other')
        rut = self.env.ref('l10n_uy.it_rut')
        currency_id = self.env['res.currency'].search([('name', '=', invoice.get('moneda'))], limit=1)
        if not currency_id:
            currency_id = self.env['res.currency'].search([('name', '=', 'UYU')], limit=1)
        l10n_latam_document_type_id = self.env['l10n_latam.document.type'].search(
            [('code', '=', str(invoice.get('tipo_comprobante', ''))), ('country_id', '=', company_id.country_id.id)], limit=1)
        serie = invoice.get('serie', '')
        num = int(invoice.get('numero', 0))
        if l10n_latam_document_type_id.doc_code_prefix and str(invoice.get('tipo_comprobante', '')) not in ['182']:
            name = "%s %s%07d" % (str(l10n_latam_document_type_id.doc_code_prefix), serie, num)
        else:
            name = "%s%07d" % (serie, num)
        vat = invoice.get('cliente', {}).get('documento', '')
        partner_id = self.env['res.partner'].search([('vat', '=', vat)], limit=1)
        if str(invoice.get('tipo_comprobante', '')) in ['182']:
            payment_id = self.env['account.payment'].search([('ref', '=', name), ('partner_id.vat', '=', vat)])
            if not payment_id:
                if not partner_id:
                    state_id = self.env['res.country.state'].search([('name', '=', invoice.get('cliente', {}).get('sucursal', {}).get('departamento', '')),
                                                                     ('country_id.code','=', 'UY')], limit=1)
                    partner_vals = {
                        'name': invoice.get('cliente', {}).get('razon_social', ''),
                        'uy_tradename': invoice.get('cliente', {}).get('nombre_fantasia', ''),
                        'vat': vat,
                        'street': invoice.get('cliente', {}).get('sucursal', {}).get('direccion'),
                        'city':invoice.get('cliente', {}).get('sucursal', {}).get('ciudad'),
                        'state_id': state_id.id,
                        'l10n_latam_identification_type_id': rut.id,
                        'country_id': self.env.ref('base.uy').id
                    }
                    try:
                        partner_id = self.env['res.partner'].create(partner_vals)
                    except Exception as e:
                        partner_vals['l10n_latam_identification_type_id'] = other.id
                        partner_id = self.env['res.partner'].create(partner_vals)
                vals = {}
                vals['payment_type'] = 'inbound'
                vals['currency_id'] = currency_id.id
                vals['partner_id'] = partner_id.id
                vals['amount'] = float(invoice.get('total', 0.0))
                vals['ref'] = name
                # vals['communication'] = name
                vals['date'] = invoice.get('fecha', False)
                # vals['uy_cfe_serie'] = invoice.get('serie', '')
                # vals['uy_cfe_number'] = str(invoice.get('numero', ''))
                # vals['uy_res_cfe_id'] = str(invoice.get('id', False))
                try:
                    new_payment_id = self.env['account.payment'].create(vals)
                    new_payment_id.write({'uy_cfe_serie': serie,
                    'uy_cfe_number': num,
                    'uy_res_cfe_id': str(invoice.get('id', False)),})
                    new_payment_id.message_post(body=json.dumps(invoice, indent=4))
                except Exception as e:
                    _logger.info(e)
        else:
            invoice_id = self.search([('name', '=', name), ('partner_id.vat', '=', vat)])
            if not invoice_id:
                if not partner_id:
                    state_id = self.env['res.country.state'].search(
                        [('name', 'ilike', invoice.get('cliente', {}).get('sucursal', {}).get('departamento', '')),
                         ('country_id.code', '=', 'UY')], limit=1)
                    partner_vals = {
                        'name': invoice.get('cliente', {}).get('razon_social', ''),
                        'uy_tradename': invoice.get('cliente', {}).get('nombre_fantasia', ''),
                        'vat': vat,
                        'street': invoice.get('cliente', {}).get('sucursal', {}).get('direccion'),
                        'city': invoice.get('cliente', {}).get('sucursal', {}).get('ciudad'),
                        'state_id': state_id.id,
                        'l10n_latam_identification_type_id': rut.id,
                        'country_id': self.env.ref('base.uy').id
                    }
                    try:
                        partner_id = self.env['res.partner'].create(partner_vals)
                    except Exception as e:
                        partner_vals['l10n_latam_identification_type_id'] = other.id
                        partner_id = self.env['res.partner'].create(partner_vals)

                move_type = str(invoice.get('tipo_comprobante', '')) in ['101', '103', '111', '113', '121', '123', '151',
                                     '153'] and 'in_invoice' or 'in_refund'

                vals = {
                    'name': name,
                    'partner_id': partner_id.id,
                    'move_type': move_type,
                    'currency_id': currency_id.id,
                    'invoice_date': invoice.get('fecha_emision', False),
                    'date': invoice.get('fecha_emision', False),
                    'invoice_date_due': invoice.get('fecha_vencimiento', False) or  invoice.get('fecha_emision', False),
                    'uy_document_code': str(invoice.get('tipo_comprobante', '')),
                }
                tax_ids = self.env['account.tax']
                if invoice.get('tot_iva_tasa_bas')>0.0:
                    tax_ids |= self.env['account.tax'].search(
                        [('company_id', '=', company_id.id), ('uy_tax_type', '=', '22'), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False)], limit=1)
                if invoice.get('tot_iva_tasa_min')>0.0:
                    tax_ids |= self.env['account.tax'].search(
                        [('company_id', '=', company_id.id), ('uy_tax_type', '=', '10'), ('type_tax_use', '=', 'purchase'),
                         ('price_include', '=', False)], limit=1)
                price_unit = float(invoice.get('total', 0.0) or '0.0') - float(invoice.get('tot_iva_tasa_bas', 0.0) or '0.0') - float(invoice.get('tot_iva_tasa_min', 0.0) or '0.0')
                vals['invoice_line_ids'] = [
                    (0, 0, {
                        'name': name,
                        'quantity': 1,
                        'price_unit': price_unit,
                        'tax_ids': tax_ids and tax_ids.ids or []
                    })
                ]
                if l10n_latam_document_type_id:
                    vals['l10n_latam_document_type_id'] = l10n_latam_document_type_id.id
                new_invoice_id = self.env['account.move'].create(vals)
                new_invoice_id.write({'uy_cfe_serie': serie,
                    'uy_cfe_number': num,
                    'uy_res_cfe_id': str(invoice.get('id', False)),})
                new_invoice_id.message_post(body=json.dumps(invoice, indent=4))
        return {}

    @api.model
    def action_uy_edi_purchase_invoice(self, days=20, date_start=None, date_end=None, company_ids=None):
        if not date_end:
            date_end = fields.Date.context_today(self)
        if not date_start:
            date_start = date_end - timedelta(days=days)
        if not company_ids:
            company_ids = self.env['res.company'].search([('country_id.code', '=', 'UY')])
        for company_id in company_ids:
            if not company_id.uy_server in ['efactura', 'biller']:
                raise UserError(_('UY is not supported for this company'))
            if company_id.uy_server in ['efactura', 'biller'] and company_id.country_id.code =='UY':
                invoices = self.env['uy.edi.send.cfe'].get_compras_cfes(date_start, date_end, company_id)
                for invoice in invoices:
                    if company_id.uy_server in ['efactura' ]:
                        self._uy_purchase_invoice_by_efactura(invoice, company_id)
                    elif company_id.uy_server in ['biller']:
                        self._uy_purchase_invoice_by_biller(invoice, company_id)
        return {}

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    uy_invoice_indicator = fields.Selection(selection="_get_uy_invoice_indicator", string="Invoice Indicator")
    uy_amount_discount = fields.Monetary("Amount Discount", compute="_compute_amount_discount")

    @api.model
    def _get_uy_invoice_indicator(self):
        return self.env['uy.datas'].get_by_code("UY.LINE.INDICATOR")

    @api.depends('price_unit', 'discount', 'currency_id')
    def _compute_amount_discount(self):
        for line in self:
            if line.display_type != 'product' or line.discount==0.0:
                line.uy_amount_discount = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit

            # Compute 'price_total'.
            if line.tax_ids and line.discount!=0.0:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                if line.move_id.uy_gross_amount == '1':
                    line.uy_amount_discount = taxes_res['total_included'] - line.price_total
                else:
                    line.uy_amount_discount = taxes_res['total_excluded'] - line.price_subtotal
            else:
                line.uy_amount_discount = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        #res = super(AccountMoveLine, self)._onchange_product_id()
        self._uy_invoice_indicator()
        return {}

    def _uy_invoice_indicator(self):
        for line in self:
            if line.tax_ids.filtered(lambda s: s.uy_tax_type == '0'):
                line.uy_invoice_indicator = '1'
            if line.tax_ids.filtered(lambda s: s.uy_tax_type == '10'):
                line.uy_invoice_indicator = '2'
            if line.tax_ids.filtered(lambda s: s.uy_tax_type == '22'):
                line.uy_invoice_indicator = '3'

    @api.onchange('uy_invoice_indicator')
    def onchange_uy_invoice_indicator(self):
        if self.uy_invoice_indicator == "1":
            tax_ids = self.tax_ids.filtered(lambda s: s.uy_tax_type == '0')
            if not tax_ids:
                taxes = self.env['account.tax'].search(
                    [('uy_tax_type', '=', '0'), ('company_id', '=', self.company_id.id)]).ids
                self.tax_ids = taxes
        elif self.uy_invoice_indicator == "2":
            tax_ids = self.tax_ids.filtered(lambda s: s.uy_tax_type == '10')
            if not tax_ids:
                taxes = self.env['account.tax'].search(
                    [('uy_tax_type', '=', '10'), ('company_id', '=', self.company_id.id)]).ids
                self.tax_ids = taxes
        elif self.uy_invoice_indicator == "3":
            tax_ids = self.tax_ids.filtered(lambda s: s.uy_tax_type == '22')
            if not tax_ids:
                taxes = self.env['account.tax'].search(
                    [('uy_tax_type', '=', '22'), ('company_id', '=', self.company_id.id)]).ids
                self.tax_ids = taxes
        elif self.uy_invoice_indicator in ["6", "7"]:
            self.tax_ids = []

