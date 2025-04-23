from odoo import fields, models, api, _
from odoo.exceptions import UserError
from base64 import decodebytes
import logging
_logger = logging.getLogger(__name__)

class UyStockEdiDocument(models.Model):
    _name = 'uy.stock.edi.document'
    _inherit = ['account.edi.document']
    _description = 'Uruguayan Stock EDI Document'

    picking_id = fields.Many2one('stock.picking', string="Stock Picking")
    edi_format_id = fields.Many2one(default=lambda self: self.env.ref('l10n_uy_edi_cfe.edi_uy_cfe'))
    move_id = fields.Many2one(required=False)

    def action_sent(self):
        for edi_document_id in self:
            uy_check_cfe = edi_document_id.env.context.get('uy_check_cfe')
            if uy_check_cfe:
                _logger.info("Verificando")
                edi_document_result = self.env['uy.edi.send.cfe'].check_cfe_eresuardo_status(edi_document_id, edi_document_id)
                if not edi_document_result.get('estado'):
                    edi_document_result = self.env['uy.edi.send.cfe'].send_eresuardo(edi_document_id)
            else:
                edi_document_result = self.env['uy.edi.send.cfe'].send_eresuardo(edi_document_id)
            values = {}
            res_values = {}
            if edi_document_result.get('estado'):
                if edi_document_id.picking_id.company_id.uy_server == 'biller':
                    data = edi_document_result.get('respuesta', {})
                    if data.get('pdf'):
                        attachment_id = self.env['ir.attachment'].create({
                            'name': "%s-%s.pdf" % (data.get('serie', ''), data.get('numero', '')),
                            'datas': data.get('pdf').encode('utf-8'),
                            'res_id': self.id,
                            'res_model': 'account.edi.format',
                            'mimetype': 'application/pdf'
                        })
                    else:
                        attachment_id = False
                    if attachment_id:
                        res_values['attachment_id'] = attachment_id.id
                    values.update({
                        'name': "%s-%s" % (data.get('serie', ''), data.get('numero', '')),
                        # 'attachment_id': attachment_id,
                        'uy_cfe_serie': data.get('serie', False),
                        'uy_cfe_number': data.get('numero', False),
                        'uy_cfe_hash': data.get('hash', False),
                        'uy_cfe_id': data.get('id'),
                        'uy_constancy': data.get('cae', {}).get('numero', False),
                        'uy_constancy_serie': data.get('cae', {}).get('serie', False),
                        'uy_constancy_from': data.get('cae', {}).get('inicio') and str(
                            data.get('cae', {}).get('inicio')) or False,
                        'uy_constancy_to': data.get('cae', {}).get('fin') and str(
                            data.get('cae', {}).get('fin')) or False,
                        'uy_constancy_vto': data.get('cae', {}).get('fecha_expiracion', False),
                        'uy_security_code': data.get('hash', False) and data.get('hash', False)[-6:] or False
                        # 'blocking_level': 'error' if 'codigosError' in edi_document_result else False,
                    })
                    # if edi_document_id.picking_id.company_id.uy_verification_url:
                    #     date = (edi_document_id.picking_id.uy_eremito_date).strftime('%d/%m/%Y')
                    #     string = "%sconsultaQR/cfe?%s,%s,%s,%s,%s,%s,%s" % (edi_document_id.picking_id.company_id.uy_verification_url,
                    #                                                         edi_document_id.picking_id.company_id.vat,
                    #                                                         '181',
                    #                                                         values.get('uy_cfe_serie'),
                    #                                                         values.get('uy_cfe_number'),
                    #                                                         edi_document_id.amount_total, date,
                    #                                                         values.get('uy_biller_hash'))
                    #     values['uy_url_code'] = string

                    if not values.get('error'):
                        values.update({'state': 'sent',
                        'error': False,
                        'blocking_level': False,})
                    else:
                        error = values.get('error').split(',')[0]
                        # raise ValidationError(values.get('error'))
                        if self.env['uy.datas'].search(
                                [('data_code', '=', 'UY.BILLER.ERROR'), ('code', '=', error)]):
                            values.update({'uy_error_code': error})
                        res_values['error'] = data.get('codigosError')
                        edi_document_id.picking_id.message_post(body=_('Error.<br/> %s') % data.get('codigosError'))
                        values.update({'state': 'to_cancel'})
                    if data.get('pdf', ''):
                        edi_document_id.picking_id.message_post(body=_('Sending the electronic document succeeded.<br/>'),
                                          attachments=[("%s-%s.pdf" % (
                                              data.get('serie', ''), data.get('numero', '')),
                                                        decodebytes(data.get('pdf', '').encode('utf-8')))])
                        edi_document_id.picking_id.uy_print = True
                    edi_document_id.write(values)
            else:
                if edi_document_result.get('respuesta', {}):
                    error = str(edi_document_result.get('respuesta'))
                else:
                    error = str(edi_document_result)
                res_values['error'] = error
                edi_document_id.picking_id.message_post(body=_('Error.<br/> %s') % error)
            edi_document_id.sudo().write(res_values)
            return {}