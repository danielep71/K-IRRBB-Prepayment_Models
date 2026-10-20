# Ownership and history inspection — 2026-10-20

Issue #4. Technical inspection completed; owner distribution confirmation is
**pending**. This record does not approve a model, a release, or third-party
rights. Scope is the immutable Git snapshots below, not subsequent changes.

## Scope

Fetched all advertised branch heads, tags and pull-request heads. No tags were
advertised. The repository was not shallow. Inspected all reachable history,
including the prototype branch and orphan traffic history, without executing
prototype code or modifying those branches.

| Ref | Inspected SHA |
| --- | --- |
| main | `12c55deb2c70a07bfd50fae629d23ee0371c0e5a` |
| prototype/k-prepay-0.1.0 | `e7340557a0f957ede3c232aaf4482c5f020d60a6` |
| traffic-history | `241831fa7ed80ad129b2ffc0be7331a95023cea4` |
| refs/pull/17/head | `7387ed630e7e302d19cf564a2814ee81a3d75a16` |
| refs/pull/18/head | `d303bbd60c0b6a8600e18d57ceb4ebc7bae985d5` |

Inventory: **14 commits**, including 2 merges; **53 trees** and **107 unique
blobs**. The only non-UTF-8 blob was the reviewed 136,005-byte branding PNG
(1280 × 640; no metadata entries reported by Pillow), SHA-256
`acf98fd10b85db9796f233df0ddce48f0a554368163fe8f030684f68b7f7ec18`.
No Office workbooks, archives or executable binaries were found in this scope.

## Secret scan

Gitleaks **8.30.1**, official Linux x64 release, verified against its published
checksums before execution. Archive SHA-256:
`551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`.

- Git-history scan: 12 non-merge commits scanned, 559,458 bytes, exit 0,
  **0 findings**. The two merge commits are included in the reachability
  inventory; Gitleaks reports the non-merge patches.
- Additional directory scan of all 107 unique reachable blobs: 737,522 bytes,
  exit 0, **0 findings**. This covers complete blob contents as well as patches.
- Built-in rules, no custom exclusions or baseline; inline `gitleaks:allow`
  comments ignored. Reports used 100% redaction. Both JSON reports were `[]`.
- No token values were accessed from settings or printed. Workflow references
  such as `secrets.TRAFFIC_TOKEN` are configuration references, not credentials.

Repeat after fetching the intended refs in a fresh clone:

```sh
git fetch origin '+refs/heads/*:refs/remotes/origin/*' '+refs/tags/*:refs/tags/*'
git fetch origin '+refs/pull/*/head:refs/remotes/pull/*'
git rev-list --count --all
gitleaks git --log-opts='--all --full-history' --ignore-gitleaks-allow --redact=100 --report-format=json --report-path=history-scan.json .
```

For the complete-content pass, enumerate `git rev-list --objects --all`, retain
objects whose `git cat-file -t SHA` is `blob`, export each via
`git cat-file blob SHA` into a private scratch directory, then run
`gitleaks dir --ignore-gitleaks-allow --redact=100` against that directory.
Use the same Gitleaks version and record refs, counts and exit status. Keep raw
reports outside the public repository until inspected and sanitized.

## Material and provenance review

| Material | Evidence and boundary |
| --- | --- |
| Root licence | MPL-2.0 text byte-identical to the pinned NMD reference in the provenance register; this is not proof of ownership of other files. |
| Setup adaptations | NMD and SACCR reference commits and local paths recorded in the register; no historical owner approval copied. |
| Branding | Editable SVG and PNG reviewed in #12; no employer logo, model results or validation claim. |
| Traffic history | Aggregate counts, referrers and paths only; no visitor identities. Public storage is documented. |
| Prototype | Separate branch at the SHA above; its reference model generates loans with `random.Random(20261020)` and history with `random.Random(7)`, using synthetic IDs such as `L0001`. No workbook is committed. This supports the synthetic-data description; it does not prove authorship or validate calculations. |
| Prototype sources | Methodology names BCBS d368 and Regulation (EU) 2024/856. This inspection does not verify regulatory accuracy or adoption of the prototype's methodology; #14 and #15 remain separate. |
| Attribution limitation | The prototype refers to SACCR template styling without an immutable source revision for that adaptation. Owner must identify any actual imported source and confirm rights; a same-account repository is not proof of ownership. |

A heuristic sweep of the 106 UTF-8 blobs found only public documentation,
repository, badge and standards URL hosts, and the already-public maintainer
reporting email. No matching private-network URL was found. Ownership and
confidentiality keyword hits were inspected as policy text, licence wording,
module state-ownership headings, methodology language or empty workbook
properties. This is a limited content review, not a guarantee that text or
model logic cannot be confidential.

## Owner confirmation required

Issue #4 explicitly requires an ownership/distribution review. The maintainer
must confirm, for the snapshots above:

1. Original source, documentation, synthetic generators and artwork are owned
   by the contributor or authorised for public distribution under the stated
   project licence.
2. Imported/adapted material has compatible rights and adequate attribution;
   identify any missing source provenance, including the prototype's SACCR
   styling reference, before marking this review complete.
3. No employer/client/vendor confidential material or unapproved proprietary
   code is included; any necessary third-party approval has been obtained.

A scan cannot establish these facts. Work authorisation is not an ownership
attestation. Record the owner's actual confirmation and any qualifications;
do not infer employer approval or reuse an approval from NMD/SACCR.

## Limits

Reachable Git objects only: no claim about unreachable/deleted server objects,
GitHub attachments, issues/comments, wiki history, releases, Actions logs,
external links or untracked local files. Secret scanners can miss credentials;
keyword searches cannot determine confidentiality or intellectual-property
rights. Reassess new content and materially changed refs before distribution.
