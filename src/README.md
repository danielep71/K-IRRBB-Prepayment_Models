# Production source

The first production modules are `core/CORE_Rates.bas` and `modules/PREPAY_Rates.bas` (SMM and CPR conversions, #42); they have not been compiled or run in Excel, and there is no `workbook/` adapter yet. Supported signatures are in [`docs/PUBLIC_API.txt`](../docs/PUBLIC_API.txt). Follow [the architecture](../docs/REPOSITORY_STRUCTURE.md): independent core, supported facade and thin Excel adapters. Add source only against an agreed contract and issue. Do not copy NMD calculation modules into this project.
