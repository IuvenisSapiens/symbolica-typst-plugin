# Releasing to Typst Universe

Symbolica 0.1.0 is already published. The next release needs a new version;
do not create a new `v0.1.0` tag pointing to today's source or replace that
version in the package registry.

The [release workflow](../.github/workflows/release.yml) adapts the
[Typst community template](https://github.com/typst-community/typst-package-template/blob/main/.github/workflows/release.yml)
to build the Wasm plugin and check its documentation before distributing it.
It does not publish the Rust crate to crates.io.

## Prepare a version

Update `typst.toml` and the package imports in both READMEs and Typst examples.
Update the version in the README's local installation path as well.
Record the changes in `CHANGELOG.md`, regenerate the manual with
`nix run .#manual`, and commit the result. The Rust crate's version can advance
separately from the Typst package version.

`README.md` describes the repository and development workflow.
`README-universe.md` is the package documentation; packaging copies it to
`README.md` in the submission. Its examples must use the release version and
compile with the staged package. Relative links to the
manual and examples are retained: those files belong in the registry submission
even though `typst.toml` excludes them from runtime downloads.

## Dry run

Choose **Prepare and release Typst package → Run workflow** in GitHub Actions.
This builds, tests, and uploads artifacts only. It does not create a GitHub
release or push to the registry fork, even if run against a tag. A dry run can
use the current manifest version while preparing an update to an already
published package.

The workflow tests the reusable library and plugin, rebuilds Wasm, checks the
examples and committed manual, and compiles the release README snippets against
the staged package. It uploads:

- `symbolica-VERSION.tar.gz`: the runtime package.
- `symbolica-VERSION-universe.tar.gz`: the complete registry submission,
  including README-linked documentation under `packages/preview/symbolica/VERSION`.
- `symbolica-VERSION-source.tar.gz`: matching source and vendored dependencies.
- `symbolica-VERSION-manual.pdf` and `SHA256SUMS`.

`SOURCE.json` inside the package identifies the source revision and checksums
for the Wasm and dependency lockfile. Inspect the artifacts before tagging.
Artifact retention is 30 days; actual releases retain their downloadable assets.

For a local metadata check, run:

```sh
nix develop -c python3 scripts/release.py preflight
```

## Publish a new version

Push a `vVERSION` tag matching the committed `typst.toml`. The workflow rejects
mismatched tags, outdated package imports, and versions already present in
`typst/packages`. A registry lookup failure also stops publication.

After validation, it creates a GitHub release containing the same artifacts.
The corresponding source revision must remain publicly accessible.

To also prepare a Universe submission, configure these repository settings
before pushing the tag:

- Variable `REGISTRY_FORK`: your fork of `typst/packages`, such as `lcnbr/packages`.
- Secret `REGISTRY_TOKEN`: a token with permission to read the upstream registry
  and push repository contents to that fork.

With no `REGISTRY_FORK`, the workflow creates only the GitHub release. With the
fork configured, it starts from current upstream `main`, copies the complete
submission, and pushes a new `release/symbolica-VERSION` branch without force.
Existing versions and existing submission branches cause an error. The job
summary links to the comparison page for opening a PR to `typst/packages`.

Review and submit that PR as the existing package maintainer. Universe
publication occurs after the registry maintainers merge the PR and its
deployment completes; creating the GitHub release alone does not publish to
Universe. See the [registry submission instructions](https://github.com/typst/packages/blob/main/docs/README.md).
