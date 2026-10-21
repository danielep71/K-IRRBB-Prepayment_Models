# VBA house style

Requirements for future source; no VBA exists on main yet.

- Use Option Explicit, four-space indentation and typed variables. Role prefixes: CORE_, PREPAY_, WB_, TEST_. Core standard modules use Option Private Module.
- State units, bounds, outputs, assumptions and failure behaviour at public boundaries. Introduce the supported-signature manifest with the first facade.
- Keep core independent of Excel/UI. Avoid implicit coercion, locale-dependent parsing, unqualified worksheet references and hidden unit conversion.
- Validate before writing outputs; invalidate stale results on failure. Never present partial results as current.
- Capture primary failure before cleanup. Restore only state owned by the operation and report cleanup failure separately. Avoid broad On Error Resume Next.
- Preserve immutable parameter sets with data/code provenance; no silent recalibration during export/scoring.
- Exported VBA and companion form binaries become authoritative source. Preserve headers/encoding. Synchronizers must distinguish exported attributes from editable document-module code.
- Require meaningful boundary/error tests and independent references. Static checks cannot establish VBA compilation or execution.

See [architecture](REPOSITORY_STRUCTURE.md), [installation](../INSTALLATION.md) and [contribution guide](../CONTRIBUTING.md).
