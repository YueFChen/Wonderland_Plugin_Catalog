# Wonderland Plugin Catalog

Public, reviewed plugin registry for Wonderland Assistant. Plugin packages and signed update manifests stay in their authors' own GitHub Releases.

- Catalog submission and publishing instructions: [catalog/README.md](catalog/README.md)
- Plugin identity records: [catalog/v2/plugins/](catalog/v2/plugins/)
- Index schema: [catalog/v2/index.schema.json](catalog/v2/index.schema.json)
- First-time repository setup: [REPOSITORY_SETUP.md](REPOSITORY_SETUP.md)

The Core client reads the generated `catalog/v2/index.json` from GitHub Pages. The index is built from reviewed per-plugin identity records in `catalog/v2/plugins/`; it is not edited or committed directly. A record pins the plugin repository and its Ed25519 public key once. Each plugin publishes its own signed update manifest and versioned release package, so plugin version updates do not require catalog edits.
