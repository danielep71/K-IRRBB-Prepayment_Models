# Contributing

Use a structured issue with the problem, component, acceptance criteria, exact SHA for defects and a minimal synthetic reproduction. Follow [metadata rules](docs/GOVERNANCE.md).

Propose focused task PRs to the active release branch, `release/0.2.0` for v0.2.0 - Prototype setup; the maintainer reviews and integrates it into main. Each milestone has its own release branch; see the [release guide](RELEASING.md). Link the issue, explain behaviour, run `python tools/check.py`, record limitations and await review/green checks. Preserve history. Issue work does not authorize publishing a release.

Update authoritative docs and [changelog](CHANGELOG.md). Distinguish planned features from implemented ones. Version changes to data, units and numerical contracts; keep models separate from Excel glue.

## Data, confidentiality and provenance

Submit only original or compatibly licensed material, citing adaptations and methods. Use synthetic loan histories. Do not commit borrower/bank/employer/client data, credentials, proprietary models, licensed extracts or internal URLs. Public issue/PR attachments are also disclosures. Ignoring a file does not make it safe to store/share.

Future Office assets require inspection of hidden sheets, names, cached data, links, connections, properties and executable content. Generated workbooks are not source.

## Evidence

Static checks establish repository integrity only. Future calculations need independent expected values and tolerances; Excel changes need real compile/run evidence on the candidate SHA with host version/bitness. An empty test suite or Python pass is not a substitute. See the [validation plan](docs/methodology/VALIDATION_PLAN.md) and [Excel evidence](docs/EXCEL_EVIDENCE.md).

Original contributions use [MPL-2.0](LICENSE). Report vulnerabilities privately via [security policy](SECURITY.md) and follow [conduct rules](CODE_OF_CONDUCT.md).
