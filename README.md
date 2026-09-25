# Wonderland Plugin Catalog

Public, reviewed plugin index for Wonderland Assistant. Plugin packages stay in their authors' own GitHub Releases.

- Catalog submission and publishing instructions: [catalog/README.md](catalog/README.md)
- Version 1 plugin records: [catalog/v1/plugins/](catalog/v1/plugins/)
- Index schema: [catalog/v1/index.schema.json](catalog/v1/index.schema.json)
- First-time repository setup: [REPOSITORY_SETUP.md](REPOSITORY_SETUP.md)

The Core client reads the generated `catalog/v1/index.json` from GitHub Pages. The index is built from the reviewed per-plugin JSON records in `catalog/v1/plugins/`; it is not edited or committed directly. A catalog entry pins one release asset URL and SHA-256 digest; updates are submitted as pull requests and published after review.
