# Security and private reports

Frame Studio is an early local desktop beta. The current beta is the focus for security fixes; there is no formal support SLA or security certification.

Do not publish tokens, API keys, private project databases, personal media or sensitive logs in an issue. If the repository offers **Security → Report a vulnerability**, use that private GitHub channel. If it is unavailable, open a minimal issue requesting a private reporting channel without exploit details or secrets, and wait for a maintainer response before sharing sensitive material.

Include the affected version/commit, desktop or source mode, a minimal reproduction and the expected impact. A synthetic project is preferable to personal data.

## Local trust boundary

The studio uses local HTTP services and filesystem storage. Desktop services bind to loopback; the UI and MCP use separate workflow credentials. The MCP bridge verifies the running desktop instance. These boundaries distinguish authorized workflow actions; they do not defend against an administrator or another fully trusted local process with access to the data directory.

Keep the data directory and backups private. It can contain project media, prompts, tokens and provider credentials. Review any agent/tool permissions before connecting it. Connecting a provider can transmit prompts/references and incur charges under that provider's account.

The Windows beta is unsigned. Install from this repository's Releases and compare the provided SHA256 value if needed. Never disable a security control or expose the local services to a public network as a workaround for a connection problem.
