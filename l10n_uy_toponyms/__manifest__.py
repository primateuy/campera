# -*- coding: utf-8 -*-
{
    'name': "Uruguayan toponyms",

    'summary': """Uruguayan toponyms""",

    'description': """
        Uruguayan toponyms
	    List Uruguayan toponyms
    """,
    'author': "GrupoYACCK",
    'website': "http://www.grupoyacck.com",

    'category': 'Localization/Toponyms',
    'version': '0.1',

    'depends': ['base_address_extended', 'l10n_uy_vat'],

    'data': [
        #'security/ir.model.access.csv',
        'views/res_partner_view.xml',
        'data/uy_country_data.xml',
        'data/res_country_data.xml',
    ],
}
