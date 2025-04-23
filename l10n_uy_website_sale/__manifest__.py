{
    "name": "Uruguayan eCommerce",
    "countries": ["uy"],
    "version": "0.1",
    "summary": "Be able to see Identification Type in ecommerce checkout form.",
    "category": "Accounting/Localizations/Website",
    "author": "Grupo YACCK",
    "license": "LGPL-3",
    "depends": [
        "website_sale",
        "l10n_uy",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_model_fields.xml",
        "views/templates.xml",
    ],
    # "assets": {
    #     "web.assets_frontend": [
    #         "l10n_uy_website_sale/static/src/js/website_sale.js",
    #     ],
    # },
    "installable": True,
    "auto_install": True,
}
