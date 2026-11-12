# Labels

The canonical catalogue is `.github/labels.json`; `.github/label-policy.json` selects application. The 20 labels were adapted from VBA-SACCR-Toolkit; see [provenance](PROVENANCE.md).

| Priority | Meaning |
| --- | --- |
| P1 | Confirmed calculation bug: wrong results for valid inputs (reserved for this case, labelled `bug`) |
| P2 | Release blocker or material correctness, data, robustness or maintainability defect |
| P3 | Non-blocking quality, testing, documentation or technical-debt improvement |

Meanings follow `.github/labels.json`. In this repository P2 also covers significant foundation work. Use one priority plus relevant type labels. A label is not a milestone.

`labels-sync.yml` validates PR changes read-only and reconciles on pushes to main and on manual runs from main only. Reconciliation removes labels outside the catalogue, but refuses, before changing anything, to delete one that is still on an issue or pull request: update the manifest intentionally when changing taxonomy. `labels-drift.yml` checks daily at 05:17 UTC and reports without mutating labels.

`bug` marks a reported or confirmed defect: the bug form applies it to every report, and I confirm the defect at triage. `blocked` is set exactly while the issue's *Dependencies* section names an open prerequisite or an external condition. Issue metadata enforcement fills the owner and milestone and never sets or changes a priority; the read-only *Issue triage* workflow reports a missing or extra priority and a wrong `blocked`. See [governance](GOVERNANCE.md).
