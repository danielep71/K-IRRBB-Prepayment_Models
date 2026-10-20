# Project branding

[prepayment-social-preview.svg](prepayment-social-preview.svg) is the editable
source. [prepayment-social-preview.png](prepayment-social-preview.png) is its
1280 × 640 raster export, used both in the root README and in GitHub's
**Settings → General → Social preview**. Keep the two files together.

The design uses the sibling NMD preview's dark background, large project name,
VBA mark and scope panels, with a blue/violet palette. The layout was redrawn
as self-contained SVG; text and shapes remain editable. There are no external
fonts, scripts, linked images, model curves or numerical results. It uses
DejaVu Sans and DejaVu Sans Mono, with system fallbacks.

All three panels describe **planned scope**. The status is **Repository setup**,
and the footer explicitly says no model, workbook or validated outputs have
been delivered. These labels must be reviewed when capabilities change.
The graphic is project branding, not a model-validation statement or an
endorsement by an employer. No employer name or logo is used.

## Provenance

Visual reference: K-IRRBB-NMDs at immutable commit
`973501c82f2f9011acfdc9d741ab2af0132cb96c`, files
`docs/assets/IRRBB_social_preview.html`, `docs/assets/IRRBB_social_preview.png`
and `docs/assets/README.md`. No NMD figures, regulatory caps, model curves,
backtest results or validation claims were imported. See the structured
[provenance register](../provenance.json). The ownership review in issue #4
remains separate from completion of this branding task.

## Edit and export

Edit the SVG text, colours and geometry, then render with CairoSVG 2.8.2:

```sh
python -m pip install CairoSVG==2.8.2
cairosvg docs/assets/prepayment-social-preview.svg -o docs/assets/prepayment-social-preview.png
```

This optional design dependency is not required by CI or model tooling.
Use DejaVu fonts for the reviewed layout; replacement fonts may change spacing.
Inspect the rendered PNG before committing, including at half size.
Keep it at 1280 × 640 and under 1 MB. The baseline integrity gate allows only
this specific PNG and verifies its committed SHA-256; all other binary files
remain subject to the existing restrictions. Update the expected digest in
`tools/check.py` deliberately whenever the image changes.

Upload the PNG through **Settings → General → Social preview → Edit → Upload
an image**. After saving, check the settings thumbnail and README rendering.
No release number appears on the image, avoiding a false release claim.
