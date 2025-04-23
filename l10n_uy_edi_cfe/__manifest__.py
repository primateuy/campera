# -*- coding: utf-8 -*-
{
    'name': "Uruguayan EDI",

    'summary': """
        Account, Uruguayan EDI""",

    'description': """
        Uruguayan EDI
    """,

    'author': "Grupo YACCK",
    'website': "http://www.grupoyacck.com",

    'category': 'Accounting/Accounting',
    'version': '4.1',

    # any module necessary for this one to work correctly
    'depends': [
        'account',
        'uom',
        'account_edi',
        'account_debit_note',
        'stock',
        'l10n_uy_datas',
        'l10n_uy_toponyms',
        'l10n_uy_vat',
        ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/uy.datas.csv',
        'data/account_edi_data.xml',
        'data/edi_data.xml',
        'views/account_move_view.xml',
        'views/account_view.xml',
        'views/currency_view.xml',
        'views/uom_view.xml',
        'views/company_view.xml',
        'views/res_config_settings_views.xml',
        'views/report_invoice.xml',
        'views/account_payment_view.xml',
        'wizard/uy_cfe_wizard_view.xml',
        'wizard/uy_cfe_purchase_sync_views.xml',
        'views/stock_picking_views.xml',
        'views/stock_picking_type_views.xml',
    ],
    'external_dependencies': {
        'python': ['pyCFE','qrcode'],
    }
}
