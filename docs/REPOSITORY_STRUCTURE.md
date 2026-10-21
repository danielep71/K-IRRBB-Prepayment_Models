# Repository structure

The project uses the **application** profile, consistent with K-IRRBB-NMDs. The intended deliverable is an analysis workbook assembled from exported VBA source. This milestone establishes the architecture; no workbook or VBA component exists yet.

| Location | Responsibility |
| --- | --- |
| src/ | Production source and approved template assets |
| tests/ | Synthetic fixtures, independent expected results and regression tests |
| examples/ | Small examples using the public facade |
| docs/ | Architecture, methodology, governance and evidence contracts |
| tools/ | Build and verification tooling, not model calculations |
| .github/ | Forms, labels and workflows |

Create each subdirectory with its first real file; current directories have guides.

## Planned boundaries

The dependency direction is **Excel adapter → public facade → calculation core**.

- `src/core/`: arrays and scalars only; no workbook objects, UI, filesystem, network or COM dependencies. Standard modules use `CORE_` and `Option Private Module`.
- `src/modules/`: supported `PREPAY_` entry points. Validate units, bounds, ordering and shapes; delegate calculations to core.
- `src/workbook/`: read sheets, call the facade, display diagnostics and write outputs. No model formulas.
- `src/classes/` and `src/forms/`: introduce only when justified.
- `tests/modules/`: `TEST_` procedures may test core directly; exclude tests from production packaging.
- Examples call only the supported facade.

These are design/review rules, not claims of an implemented VBA boundary checker. Introduce a reviewed `docs/PUBLIC_API.txt` with the first facade, listing normalized supported signatures rather than every Public declaration.

## Units and provenance

Rates and probabilities use decimals; rates identify annualisation. Monetary amounts carry an ISO currency. Dates, observation frequency, endpoints, CPR/SMM denominators and loan-event definitions are specified in the [data contract](methodology/DATA_CONTRACT.md) and [model contracts](methodology/MODEL_CONTRACTS.md) proposed in issue #14; they must be accepted before implementation. No implicit FX conversion or annual/monthly probability substitution is allowed.

Freeze each future parameter set with an ID, model/version, segment/currency, data window and fingerprint, calibration settings, values/units, diagnostics, timestamp and exact code SHA. Changes create new sets. Scenarios, backtests and exports identify the set used; exporting must not silently recalibrate.

## Artifacts and runtime

Exported VBA will be authoritative. Built workbooks, local evidence and parameter exports are ignored. No workbook exception is approved. A future macro-free template needs an exact-path exception, reproducible preparation, inspection and its own issue.

The intended runtime is Windows Excel 64-bit without Python, R or external services. Independent benchmark tooling can use other languages. Full IRRBB aggregation, pricing, automatic ALM uploads and model approval are outside setup scope.
