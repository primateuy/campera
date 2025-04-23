# -*- coding: utf-8 -*-
from odoo import api, fields, models
from pdf2image import convert_from_bytes
from base64 import decodebytes, encodebytes
from io import BytesIO

class PosOrder(models.Model):
    _inherit = 'pos.order'

    uy_uuid = fields.Char("Uuid Uruguayan", copy=False)

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        if not ui_order.get('partner_id'):
            res['partner_id'] = self.env['pos.config'].browse(ui_order['pos_session_id']).uy_anonymous_id.id
        if ui_order.get('uy_uuid'):
            res['uy_uuid'] = ui_order['uy_uuid']
        return res
    
    # def _prepare_invoice_lines(self):
    #     invoice_lines = super(PosOrder, self)._prepare_invoice_lines()
    #     new_invoice_lines = []
    #     for invoice_line in invoice_lines:
    #         
    # 
    # 
    #     if order_line.tax_ids_after_fiscal_position.filtered(lambda s:s.uy_tax_type == '0'):
    #         res['uy_invoice_indicator'] = '1'
    #     if order_line.tax_ids_after_fiscal_position.filtered(lambda s:s.uy_tax_type == '10'):
    #         res['uy_invoice_indicator'] = '2'
    #     if order_line.tax_ids_after_fiscal_position.filtered(lambda s:s.uy_tax_type == '22'):
    #         res['uy_invoice_indicator'] = '3'
    #     return res
    
    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        reversed_entry_ids = self.mapped('refunded_order_ids')
        reversed_entry_id = reversed_entry_ids and reversed_entry_ids[0] or False
        company_id = self.company_id.parent_id or self.company_id
        if self.uy_uuid:
            res['uy_uuid'] = self.uy_uuid
        if reversed_entry_id:
            res['reversed_entry_id'] = reversed_entry_id.account_move.id
        if self.partner_id.uy_doc_type=='2' and res.get('move_type', '') == 'out_refund':
            journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('uy_document_code', '=', '112'),
                 ('company_id', '=', company_id.id),('uy_is_edi_document','=',True)], limit=1)
            if journal_id:
                res['uy_document_code'] = '112'
                res['journal_id'] = journal_id.id

        elif self.partner_id.uy_doc_type!='2' and res.get('move_type', '') == 'out_refund':
            journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('uy_document_code', '=', '102'),
                 ('company_id', '=', company_id.id),('uy_is_edi_document','=',True)], limit=1)
            if journal_id:
                res['uy_document_code'] = '102'
                res['journal_id'] = journal_id.id
        elif self.partner_id.uy_doc_type=='2':
            journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('uy_document_code', '=', '111'),
                 ('company_id', '=', company_id.id),('uy_is_edi_document','=',True)], limit=1)
            if journal_id:
                res['uy_document_code'] = '111'
                res['journal_id'] = journal_id.id
        else:
            journal_id = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('uy_document_code', '=', '101'),
                 ('company_id', '=', company_id.id),('uy_is_edi_document','=',True)], limit=1)
            if journal_id:
                res['uy_document_code'] = '101'
                res['journal_id'] = journal_id.id
        return res
    
    def get_uy_pdf_invoice(self):
        self.ensure_one()
        vals = {}
        move_id = self.account_move.sudo()
        if not move_id.uy_print:
            move_id.action_check_cfe_pdf_status()
        edi_document_id = move_id.uy_cfe_id
        if edi_document_id.attachment_id:
            vals['url'] = '/web/content/ir.attachment/%d/datas/%s' % (edi_document_id.attachment_id.id, edi_document_id.attachment_id.name)

            images = convert_from_bytes(decodebytes(edi_document_id.attachment_id.datas))
            all_images = []
            # Proecess image
            for i in range(len(images)):
                # image = Image.frombytes(images[i])
                grayscale = images[i].convert('L')
                # BW = image.convert('1')
                file = BytesIO()
                grayscale.save(file, 'png')
                image_b64 = encodebytes(file.getvalue())
                width = grayscale.width % 2 != 0 and grayscale.width + 1 or grayscale.width
                all_images.append(
                    {
                        'image': image_b64,
                        'height': grayscale.height,
                        'width': width
                    }
                )
            vals['invoice'] = all_images[0]
        if edi_document_id.error:
            vals['error'] = edi_document_id.error

        return vals

    def _export_for_ui(self, order):
        res = super(PosOrder, self)._export_for_ui(order)
        res['uy_order_server_id'] = order.id
        return res
    def _create_invoice(self, move_vals):
        res = super(PosOrder, self.with_context(uy_edi_pos_document=True))._create_invoice(move_vals=move_vals)
        res.invoice_line_ids._uy_invoice_indicator()
        if self.uy_uuid:
            res.uy_uuid = self.uy_uuid
        return res
    
#class PosOrderLine(models.Model):
#    _inherit = "pos.order.line"
    
    
    
