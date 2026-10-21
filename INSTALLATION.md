# Developer installation

There is no workbook, add-in or prepayment engine to install yet.

## Current prerequisites

Git, **Python 3.10+** and **Node.js 22+**. Baseline checks use standard libraries: no package installation, token or Excel instance is required.

```sh
git clone https://github.com/danielep71/K-IRRBB-Prepayment_Models.git
cd K-IRRBB-Prepayment_Models
python tools/check.py
```

The command validates repository files/configuration, runs metadata regression tests and label-script self-tests. The full CI gate also validates YAML/workflows and runs Python lint/type checks; its pinned-tool installation is documented in the tooling guide. See [tooling](tools/README.md).

## Intended Excel support

Future runtime development targets **Windows Excel 64-bit**, using default VBA, Excel, Office and OLE Automation references. No Excel certification exists yet. 32-bit is untested and uncertified; Mac and Excel web are not supported targets. Avoid runtime Python/R, external services and non-default COM references without a reviewed design.

Import, template/build and harness instructions will arrive with implementation. Do not change macro security or trust settings for today's checks.

Follow [house style](docs/VBA_HOUSE_STYLE.md) and [architecture](docs/REPOSITORY_STRUCTURE.md). Git uses CRLF working-tree VBA/Windows scripts and LF cross-platform text. VBE encoding is not forced to UTF-8 without round-trip evidence. Keep generated output outside committed source.
