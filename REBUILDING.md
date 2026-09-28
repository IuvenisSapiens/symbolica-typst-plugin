# Source locations and rebuilding

The plugin source, `Cargo.lock`, and build scripts are available in the
[upstream repository](https://github.com/symbolica-dev/symbolica-typst-plugin).
Version 0.1.0 is published on Typst Universe. Future releases use a matching
`v<version>` tag and include `SOURCE.json` with the exact source revision and
hashes of the engine and dependency lockfiles. See the repository's
[release instructions](https://github.com/symbolica-dev/symbolica-typst-plugin/blob/main/docs/releasing.md).

Dependencies are fetched from crates.io at the versions and checksums recorded
in `Cargo.lock`, or from Git at the recorded commit. Symbolica uses `main` at
[`06906976bca24fefc5203aee699d90d62ebe08cd`](https://github.com/symbolica-dev/symbolica/tree/06906976bca24fefc5203aee699d90d62ebe08cd).
Versioned dependencies and the root crates.io patch keep the plugin, integration
engine, and reusable payload modules on this revision. [Third-party notices](THIRD_PARTY_LICENSES.txt) provide
exact source archive URLs and Git revisions for the Wasm build.

The root `[patch.crates-io]` table selects the Symbolica source. Change or replace
that entry to select another compatible Git revision or local checkout, then
update the lockfile. There is no direct Git dependency on Symbolica that would
bypass the patch. The payload implementation is part of `symbolica-typst-plugin`;
there is no separate payload crate or patch entry.

When embedding the library in another workspace, that workspace supplies its
own Symbolica patch. Cargo does not inherit patch tables from dependencies.
To use the revision above, add this at the consuming workspace's root:

```toml
[patch.crates-io]
symbolica = { git = "https://github.com/symbolica-dev/symbolica.git", rev = "06906976bca24fefc5203aee699d90d62ebe08cd" }
```

## Build

Check out the source revision matching the binary. Install Rust 1.97.0, its
`wasm32-unknown-unknown` standard library, and Binaryen 130 (`wasm-opt`), then run:

```sh
bash scripts/build-engine.sh
```

The build uses `cargo rustc --locked`, so it retains the recorded Git revision
even when `main` advances. Update the lockfile explicitly when upgrading
dependencies. Cargo downloads the locked dependencies. The result is
`symbolica/symbolica.wasm`. The release profile uses the default 16 codegen
units, full LTO, and no Wizer preinitialization. Rust uses `opt-level = "s"`
except for the generated `symbolica-integrate` rule code, which stays at `"z"`.
Binaryen still applies `-Oz`. This mixed profile improves rule initialization
while keeping the measured runtime archive below 8,000,000 bytes (8 MB).
See [the optimization measurements](https://github.com/symbolica-dev/symbolica-typst-plugin/blob/main/docs/wasm-optimization.md).

Normal Cargo builds produce a reusable Rust library (`rlib`). Its default
`native` feature uses Symbolica's native GMP/MPFR backend. For Wasm, disable
defaults and select `wasm`. The independent `plugin` feature enables the Typst
entry points, integration engine, and plugin runtime setup; other plugins using
the shared library should leave it disabled.

The build script explicitly selects `cdylib` when producing the standalone
plugin, then optimizes that Wasm module:

```sh
cargo rustc --locked --release --target wasm32-unknown-unknown \
  --package symbolica-typst-plugin --lib --crate-type cdylib \
  --no-default-features --features wasm,plugin
```

Run the library and full native plugin tests with:

```sh
cargo test --locked
cargo test --locked --features plugin
```

Before publishing the crate, select and validate a crates.io release of
Symbolica, including its Atom export compatibility. The current build remains
pinned to the Git revision above. The Cargo package includes Rust sources,
tests, the README, and license; generated Wasm and the manual PDF are distributed
with the Typst package separately.

To rebuild with a modified dependency whose license permits modification,
add a Cargo `[patch.crates-io]` path override, update the lockfile as needed,
and rebuild. For example:

```toml
[patch.crates-io]
malachite-base = { path = "modified/malachite-base" }
```

Symbolica's own source remains governed by `LICENSE-SYMBOLICA.md` and the
limited permission in `LICENSE-SYMBOLICA-TYPST.md`.

## Optional offline archive

Maintainers can run `python3 scripts/prepare-source.py` to generate
`dist/symbolica-0.1.0-source.tar.gz`, containing the plugin source and vendored
dependencies, including the locked Git checkout and Cargo source replacements
needed to rebuild without fetching dependencies. This is an optional convenience
and availability backup, not a required archive format. It is not included in the Typst runtime package.

Source access must remain available to binary recipients. Hosting sources on
crates.io or GitHub does not remove the distributor's responsibility to ensure
their availability. See `THIRD_PARTY.md` for the applicable licenses.
