# FastPDLC

**Product-as-code as a validated graph — for any project.**

Your product intent — the glossary, the constraints, the business rules, the
features, the decisions — usually lives as hopeful markdown that quietly rots. FastPDLC
turns it into **code**: you declare your typed artifacts in one config file, and it
loads them, enforces the schema and the cross-references, compiles a JSON bundle your
app or docs can render, and **fails CI when the committed bundle drifts**.

It started as the product-as-code engine inside a payments platform and was extracted
so any team can use it.

```bash
pip install fastpdlc
```

## Quickstart

1. Describe your artifact types in `product.config.yaml`:

   ```yaml
   product_dir: product
   output: build/product.generated.json
   types:
     - name: terms                 # a glossary
       dir: terms
       id_prefix: "TERM-"          # ids must be TERM-<slug> and match the filename
       required: [id, term, definition]
       fields: [term, definition, see_also]
       references:
         - field: see_also         # every see_also must resolve to another term
           to: terms
     - name: rules                 # the durable invariants
       dir: rules
       id_prefix: "BR-"
       required: [id, title, statement]
       fields: [title, statement]
   ```

2. Author artifacts as markdown-with-frontmatter under `product/`:

   ```markdown
   ---
   id: TERM-payment
   term: Payment
   definition: An instruction to move money between two parties.
   see_also: [TERM-ledger]
   ---
   The canonical unit of work in the system.
   ```

3. Build the bundle and gate it in CI:

   ```bash
   fastpdlc build       # -> build/product.generated.json  (commit it)
   fastpdlc validate    # schema + graph + staleness; non-zero exit on errors
   ```

## What `validate` enforces

Every finding carries a stable `PAC-NNN` code (an API — CI and dashboards match on the
code, never the prose):

| code | meaning |
|---|---|
| `PAC-001` | an artifact is missing a required field |
| `PAC-010` | an id doesn't start with its type's `id_prefix` |
| `PAC-011` | an id doesn't match its filename |
| `PAC-012` | a duplicate id within a type |
| `PAC-020` | a reference field doesn't resolve to a known artifact |
| `PAC-030` | a field value isn't in the type's allowed set (`enums`) |
| `PAC-060` | the committed generated bundle is missing or stale |

## Config reference

Each entry under `types`:

- **`name`** — the collection name (and the key in the bundle).
- **`dir`** — the subdirectory under `product_dir`.
- **`id_prefix`** *(optional)* — required id prefix; with **`id_matches_filename`**
  (default `true`), the id must equal the filename stem.
- **`required`** — frontmatter fields that must be present and non-empty (`id` always is).
- **`fields`** — the fields captured into the bundle.
- **`enums`** — `field -> [allowed values]`.
- **`references`** — `[{ field, to }]`: values of `field` must be the id of a `to` artifact.

## Extending it — plugins

Real projects need more than schema: cross-file checks ("does this `links.code` path
exist?"), derived bundle fields (reverse edges, rollups), extra generated outputs (a
runtime catalogue), and their own diagnostic codes. A **plugin** registers those without
forking the engine — which is how a large project migrates onto FastPDLC with **no loss
of functionality**:

```python
# product_hooks.py
from fastpdlc import register

def register(reg):
    register("PAC-900", "links.code path does not exist on disk")

    @reg.validator
    def code_paths_exist(bundle, config, root, report):
        for f in bundle["features"]:
            for path in f.get("code") or []:
                if not (root / path).exists():
                    report.add("PAC-900", f"missing {path}", f["_file"])

    @reg.bundle_transformer
    def reverse_edges(bundle, config, root):
        ...  # enrich the bundle in place

    reg.extra_output("build/catalogue.json", render_catalogue)  # staleness-gated too
```

```bash
fastpdlc -p product_hooks.py validate
```

## CI

```yaml
# .github/workflows/product.yml
name: product-as-code
on: [pull_request, push]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install fastpdlc
      - run: fastpdlc validate
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
