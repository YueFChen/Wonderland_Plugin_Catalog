# First-time GitHub setup

Create a **public** GitHub repository named `Wonderland_Plugin_Catalog`, push this directory to its `main` branch, then:

1. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
2. In **Settings → Rules → Rulesets**, create an active branch ruleset for `main`.
3. Require a pull request before merging, at least one approving review, and the `validate` status check. Dismiss stale approvals when new commits are pushed and block force pushes/deletion.
4. Allow the `github-pages` Actions environment to deploy from `main`.
5. Confirm the Pages URL serves `/Wonderland_Plugin_Catalog/catalog/v2/index.json` as JSON.

The `publish` job runs only after `validate` succeeds on a push to `main`. Pull request validation has read-only repository permissions and never receives release credentials.
