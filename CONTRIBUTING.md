# Contributing

This repository is an incubation space for the
[Tool Annotations Interest Group](https://modelcontextprotocol.io/community/tool-annotations/charter).
We welcome proposals, schema changes, and reference implementations that
inform a future Extensions Track SEP.

## What lives here

- **Specification drafts** — `specification/draft/<extension-name>.mdx`,
  one file per extension, written in the same RFC-2119 style as the core MCP
  specification (per [SEP-2133](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md)).
- **Decision records** — `docs/decisions.md`. Append, do not rewrite.
- **Open questions** — `docs/open-questions.md`.

## What does *not* live here

- Unrelated product implementation code. Small reference implementations,
  conformance fixtures, and schema generators that directly validate an
  extension MAY live in this repository under `src/`, `examples/`, and `tests/`.
  Larger SDKs and production integrations should live in their own repositories
  and be linked from the relevant `specification/draft/*.mdx`.
- Binding specification changes. Those are made through the
  [SEP process](https://modelcontextprotocol.io/community/sep-guidelines).

## Proposing a change to an existing extension

1. Open a PR against `specification/draft/<name>.mdx`.
2. Update the **Status** and **Changelog** sections in the frontmatter.
3. If the change is breaking (per the SEP-2133 definition), use a new
   extension identifier and a new file.
4. Append an entry to `docs/decisions.md` if the change reflects a design
   decision worth preserving.
5. If the extension has repository-local schemas or reference code, run
   `npm run check` and commit regenerated artifacts.

## Proposing a new extension

1. Read [SEP-2133, "Experimental Extensions"](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#experimental-extensions).
2. Open a discussion or PR proposing the identifier and scope.
3. On acceptance, add `specification/draft/<new-name>.mdx` using the
   frontmatter from an existing draft as a template.

## Code of conduct

This repository follows the
[MCP Code of Conduct](https://github.com/modelcontextprotocol/.github/blob/main/CODE_OF_CONDUCT.md).
