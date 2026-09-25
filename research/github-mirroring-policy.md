# GitHub mirror policy

The GitHub repository is a **private, curated source-of-truth mirror** for
reviewed source, tests, research notes, manifests, and lightweight provenance.
It is not a backup of the whole workstation.

Before each sync, run `scripts/github_sync_audit.py` and use
`scripts/github_sync.ps1` only after relevant local checks have passed. The
auditor excludes private data, raw media, model/binary archives, Agent Studio
state, generated artifacts, and unsupported file types; it rejects files with
recognized secret signatures. A failed audit prevents staging, committing, and
pushing.

The sync script accepts only the configured `origin` for this project and
requires an explicit commit/push invocation. It may never store a GitHub token,
copy a credential into this repository, or use a generic organization-wide
credential. Pushing is a publication event: include the check receipt in the
commit message or adjacent research note, preserve rights notices, and never
stage raw media merely to make a report look complete.

"Real-time" means immediately after a bounded, verified project change—not on
every editor save. This keeps the remote current without publishing untested
work, private material, or a misleading half-finished claim.
