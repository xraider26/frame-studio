# Orchestra frontend

This Next.js interface belongs to the local Orchestra production workflow. Start with the [project README](../README.md) and [first-project guide](../docs/GETTING-STARTED.md).

The connected application is `/studio`. It expects the local workflow API and its private data/token directory; a standalone public web deployment is not the current architecture. The older companion page at `/` uses a separate legacy API.

For source development, install dependencies with `npm ci`, run the backend through the root `launch-studio.ps1 -BackendOnly`, then run `npm run dev` here. Open `http://127.0.0.1:3000/studio`. Use `npm test` and `npm run build` to verify changes. The Windows installer packages the standalone build and starts it automatically.

`STUDIO_DATA_DIR` and `STUDIO_API_URL` are server-side runtime settings. Never expose tokens or provider keys through public environment variables. [Windows packaging](../docs/WINDOWS.md) · [Contribution boundaries](../CONTRIBUTING.md).
