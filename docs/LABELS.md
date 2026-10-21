# Labels

The canonical catalogue is `.github/labels.json`; `.github/label-policy.json` selects application. The 20 labels were adapted from VBA-SACCR-Toolkit; see [provenance](PROVENANCE.md).

| Priority | Meaning |
| --- | --- |
| P1 | Critical blocker or serious correctness, data or application-state risk |
| P2 | Material correctness, robustness or maintainability issue; significant foundation work |
| P3 | Non-blocking quality, tests, documentation or technical debt |

Use one priority plus relevant type labels. A label is not a milestone.

`labels-sync.yml` validates PR changes read-only and reconciles on trusted main pushes or manual dispatch. Reconciliation removes labels outside the catalogue: update the manifest intentionally when changing taxonomy. `labels-drift.yml` checks daily at 05:17 UTC and reports without mutating labels. Issue metadata enforcement separately fills owner/milestone and resolves priorities; see [governance](GOVERNANCE.md).
