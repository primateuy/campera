from odoo import fields, models, api, _
from odoo.exceptions import UserError
import uuid
from base64 import decodebytes

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    uy_eremito_date = fields.Date("E-Remito Date")
    uy_edi_cfe_ids = fields.One2many('uy.stock.edi.document', 'picking_id', string="CFE Documents")
    uy_uuid = fields.Char("Uuid Uruguayan", copy=False, default=lambda s: str(uuid.uuid4()))

    # Edi Detail
    uy_edi_name = fields.Char("CFE Name", compute="_compute_uy_edi_detail", store=True, copy=False)
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
    uy_attachment_id = fields.Many2one('ir.attachment', "Document", compute="_compute_uy_edi_detail", store=True,
                                       copy=False)
    uy_state = fields.Selection(
        [('to_send', 'To Send'), ('sent', 'Sent'), ('to_cancel', 'To Cancel'), ('cancelled', 'Cancelled')], compute="_compute_uy_edi_detail", store=True,
                                       copy=False)
    uy_edi_id = fields.Many2one('uy.stock.edi.document', "UY EDI", compute="_compute_uy_edi_detail", store=True,
                                copy=False)
    uy_res_cfe_id = fields.Char("Url Code", compute="_compute_uy_edi_detail", store=True, copy=False)
    uy_print = fields.Boolean("Uy Print", default=False)


    # type of transfer
    uy_edi_cfe_type = fields.Selection([
        ('1', 'Venta'),
        ('2', 'Entre establecimientos de la misma empresa'),
    ], string="CFE Type", compute='_compute_uy_edi_cfe_type', store=True, readonly=False)

    @api.depends('picking_type_id')
    def _compute_uy_edi_cfe_type(self):
        for picking in self:
            picking.uy_edi_cfe_type = picking.picking_type_id.uy_edi_cfe_type

    def validade_edi_cfe(self):
        for picking in self:
            if picking.company_id.uy_server != 'biller':
                raise UserError(_("Please configure the server Biller"))
            if not picking.partner_id:
                raise UserError(_("Please fill the partner"))
            if not picking.uy_edi_cfe_type:
                raise UserError(_("Please fill the CFE Type"))
            if not picking.partner_id.uy_doc_type:
                raise UserError(_("Please fill the Partner Document Type"))
            if not picking.partner_id.vat:
                raise UserError(_("Please fill the Partner Document Number"))
            if not picking.partner_id.street:
                raise UserError(_("Please fill the Partner Address"))
            if not picking.partner_id.city:
                raise UserError(_("Please fill the Partner City"))
            if not picking.partner_id.state_id:
                raise UserError(_("Please fill the Partner State"))

    def action_generate_edi_cfe(self):
        self.ensure_one()
        self.validade_edi_cfe()
        self.uy_eremito_date = fields.Date.context_today(self)
        if not self.uy_edi_id:
            edi_document_id = self.env['uy.stock.edi.document'].create({
                'picking_id': self.id,
                # 'name': self.uy_edi_name,
                'edi_format_id': self.env.ref('l10n_uy_edi_cfe.edi_uy_cfe').id,
                'state': 'to_send'
            })
        else:
            edi_document_id = self.uy_edi_id
        edi_document_id.action_sent()

    @api.depends('uy_edi_cfe_ids.uy_cfe_serie',
                 'uy_edi_cfe_ids.uy_cfe_number',
                 'uy_edi_cfe_ids.uy_qr_id',
                 'uy_edi_cfe_ids.uy_security_code',
                 'uy_edi_cfe_ids.uy_constancy',
                 'uy_edi_cfe_ids.uy_constancy_serie',
                 'uy_edi_cfe_ids.uy_constancy_from',
                 'uy_edi_cfe_ids.uy_constancy_to',
                 'uy_edi_cfe_ids.uy_constancy_vto',
                 'uy_edi_cfe_ids.uy_url_code',
                 'uy_edi_cfe_ids.attachment_id',
                 'uy_edi_cfe_ids.state')
    def _compute_uy_edi_detail(self):
        for picking in self:
            uy_edi_cfe_ids = picking.uy_edi_cfe_ids.filtered(lambda s: s.edi_format_id.code == 'edi_uy_cfe')
            edi_document_id = len(uy_edi_cfe_ids) > 1 and uy_edi_cfe_ids[0] or uy_edi_cfe_ids
            picking.uy_cfe_serie = edi_document_id.uy_cfe_serie
            picking.uy_cfe_number = edi_document_id.uy_cfe_number
            picking.uy_qr_id = edi_document_id.uy_qr_id
            picking.uy_security_code = edi_document_id.uy_security_code
            picking.uy_constancy = edi_document_id.uy_constancy
            picking.uy_constancy_serie = edi_document_id.uy_constancy_serie
            picking.uy_constancy_from = edi_document_id.uy_constancy_from
            picking.uy_constancy_to = edi_document_id.uy_constancy_to
            picking.uy_constancy_vto = edi_document_id.uy_constancy_vto
            picking.uy_url_code = edi_document_id.uy_url_code
            picking.uy_attachment_id = edi_document_id.attachment_id
            picking.uy_state = edi_document_id.state
            picking.uy_edi_id = edi_document_id.id
            picking.uy_res_cfe_id = edi_document_id.uy_cfe_id
            if edi_document_id.uy_cfe_serie and edi_document_id.uy_cfe_number:
                picking.uy_edi_name = "%s-%s" % (edi_document_id.uy_cfe_serie, edi_document_id.uy_cfe_number)
            else:
                picking.uy_edi_name = False

    def action_check_cfe_pdf_status(self):
        for picking in self:
            edi_document_ids = picking.uy_edi_cfe_ids.filtered(
                lambda s: s.edi_format_id.code == 'edi_uy_cfe' and s.state == 'sent')
            edi_document_id = len(edi_document_ids) > 1 and edi_document_ids[0] or edi_document_ids
            if edi_document_id:
                if not picking.uy_print:
                    res = self.env['uy.edi.send.cfe'].get_cfe_pdf(picking, edi_document_id)
                    if res.get('estado') and res.get('respuesta', {}).get('pdf', ''):
                        data = res.get('respuesta', {})
                        if data.get('pdf') and not edi_document_id.attachment_id:
                            attachment_id = self.env['ir.attachment'].create({
                                'name': "%s.pdf" % (picking.uy_edi_name),
                                'datas': data.get('pdf').encode('utf-8'),
                                'mimetype': 'application/pdf'
                            })
                            edi_document_id.sudo().attachment_id = attachment_id.id
                        picking.uy_print = True

                        picking.message_post(body=_('Sending the electronic document succeeded.<br/>'),
                                          attachments=[("%s.pdf" % (picking.uy_edi_name),
                                                        decodebytes(data.get('pdf', '').encode('utf-8')))])

                    else:
                        picking.message_post(body=_('Error.<br/> %s') % res.get('respuesta', {}))