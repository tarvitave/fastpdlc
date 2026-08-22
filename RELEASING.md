# Releasing FastPDLC

Publishing is automated: `.github/workflows/publish.yml` builds and uploads to PyPI
when a GitHub Release is published. Auth is **PyPI Trusted Publishing (OIDC)** — no
API token is stored in the repo or in Actions secrets.

## One-time PyPI setup

Do this once, before the first release. It's the only manual step.

1. Log in at <https://pypi.org>.
2. Reserve the project name by creating a **pending publisher** (no upload needed
   first): go to <https://pypi.org/manage/account/publishing/> → *Add a pending
   publisher* and fill in:
   - **PyPI project name:** `fastpdlc`
   - **Owner:** `tarvitave`
   - **Repository name:** `fastpdlc`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. (Recommended) In the GitHub repo, create an **Environment** named `pypi`
   (Settings → Environments) so the publish job's `environment: pypi` resolves and
   you can add release protection rules later.

That's it — no `PYPI_API_TOKEN`, no `twine` credentials.

## Cutting a release

1. Bump `version` in `pyproject.toml` (and note changes).
2. Commit, tag, and push:
   ```bash
   git commit -am "release: vX.Y.Z"
   git tag vX.Y.Z
   git push --follow-tags
   ```
3. Publish a **GitHub Release** from that tag (`gh release create vX.Y.Z --generate-notes`).
   That fires `publish.yml`, which asserts the tag matches `pyproject.toml`'s version,
   builds the sdist + wheel, and uploads to PyPI via OIDC.
4. Verify: `pip install fastpdlc==X.Y.Z`.

## Versioning

FastPDLC follows semver. Diagnostic **codes are API** — never renumber an existing
`PAC-NNN` (retire and add). Changing the JSON bundle shape, a config key, or the
plugin `Registry` surface is a breaking change → bump the major.
