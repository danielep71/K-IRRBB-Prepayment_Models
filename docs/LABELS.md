# Labels

The canonical catalogue is `.github/labels.json`; `.github/label-policy.json` selects application. The 20 labels were adapted from VBA-SACCR-Toolkit; see [provenance](PROVENANCE.md).

| Priority | Meaning |
| --- | --- |
| P1 | Critical release blocker or serious correctness, data or application-state risk |
| P2 | Material correctness, robustness or maintainability defect |
| P3 | Non-blocking quality, testing, documentation or technical-debt improvement |

Meanings follow `.github/labels.json`. In this repository P2 also covers significant foundation work. Use one priority plus relevant type labels. A label is not a milestone.

`labels-sync.yml` validates PR changes read-only and reconciles on trusted main pushes or manual dispatch. Reconciliation removes labels outside the catalogue: update the manifest intentionally when changing taxonomy. `labels-drift.yml` checks daily at 05:17 UTC and reports without mutating labels. Issue metadata enforcement separately fills owner/milestone and resolves priorities; see [governance](GOVERNANCE.md).
