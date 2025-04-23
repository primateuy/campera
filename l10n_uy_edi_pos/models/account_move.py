from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _generate_pdf_and_send_invoice(self, template, force_synchronous=True, allow_fallback_pdf=True, bypass_download=False, **kwargs):
        if self.company_id.country_code == "UY" :
            return {}
        return super()._generate_pdf_and_send_invoice(template, force_synchronous, allow_fallback_pdf, bypass_download, **kwargs)
