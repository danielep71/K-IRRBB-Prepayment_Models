# Contributing

Open a structured issue with the problem, the component, acceptance criteria, the exact SHA for a defect and a minimal synthetic reproduction, following the [metadata rules](docs/GOVERNANCE.md).

Propose focused task PRs to the active release branch, the branch that `target-branch` names in [`.github/dependabot.yml`](.github/dependabot.yml); I integrate it into main. Each milestone has its own release branch; see the [release guide](RELEASING.md). In your PR, link the issue, explain the behaviour, run `python tools/check.py`, record the limitations, and wait for my review and green checks. Do not rewrite history. Work on an issue does not authorize publishing a release.

Update the authoritative docs and the [changelog](CHANGELOG.md). Distinguish planned features from implemented ones. Version changes to data, units and numerical contracts; keep models separate from Excel glue.

## Data, confidentiality and provenance

Submit only original or compatibly licensed material, and cite adaptations and methods. Use synthetic loan histories. Do not commit borrower/bank/employer/client data, credentials, proprietary models, licensed extracts or internal URLs. Public issue/PR attachments are also disclosures. Ignoring a file does not make it safe to store/share.

Future Office assets require inspection of hidden sheets, names, cached data, links, connections, properties and executable content. Generated workbooks are not source.

## Evidence

Static checks establish repository integrity only. Future calculations need independent expected values and tolerances; Excel changes need real compile/run evidence on the candidate SHA with host version/bitness. An empty test suite or Python pass is not a substitute. See the [validation plan](docs/methodology/VALIDATION_PLAN.md) and [Excel evidence](docs/EXCEL_EVIDENCE.md).

Original contributions use [MPL-2.0](LICENSE). Report vulnerabilities to me privately under the [security policy](SECURITY.md), and follow the [conduct rules](CODE_OF_CONDUCT.md).
