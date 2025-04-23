# Uruguayan localization

I hope it is helpful and in the future the project can grow

```sql
UPDATE ir_module_module SET name = 'l10n_uy_edi_cfe' WHERE name = 'l10n_uy_edi';
UPDATE ir_model_data SET module = 'l10n_uy_edi_cfe' WHERE module = 'l10n_uy_edi';
UPDATE ir_model_data SET name = 'module_l10n_uy_edi_cfe' 
WHERE name = 'module_l10n_uy_edi' AND module = 'base' AND model = 'ir.module.module';
UPDATE ir_module_module_dependency SET name = 'l10n_uy_edi_cfe' WHERE name = 'l10n_uy_edi';
```