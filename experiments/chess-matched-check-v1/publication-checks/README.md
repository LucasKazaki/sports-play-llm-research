# Post-run publication checks

The [corrected check receipt](checks.json) verifies all 199 exact aliases, all 119 original cohort/run files, 20 pre-call files, 19 protocol-manifest files, copied raw/label scoring and report links. These are file-only checks; no model, engine or GPU call occurs.

The first validator mistakenly required the deliberately malformed original partial-seal regression artifact to parse as valid JSON. Its [source and error receipt](failed-checker-receipt.json) remain unchanged. The correction permits only that exact original path and SHA256, retaining byte equality checks. This is a post-run checker correction, not an experiment repair or additional inference. [Supplement manifest](manifest.json) maps these exact files; the main public manifest remains unchanged.
