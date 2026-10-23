# Image prompting and ComfyUI

The new Orchestra connector executes imported ComfyUI API workflows through the same claimed jobs, approvals, budget/dispatch checks, revision tracking and media validation as other generators. It is separate from the older companion's SD1.5 polishing tool.

## Image direction

In **Plan → Shots & direction → Story**, choose Generate or Edit and enter requested changes, what must remain unchanged, exact visible text (one item per line), layout and background/transparency intent. Bind source images and roles in References. Edit mode requires an explicit valid image binding and requested changes; it does not apply inherited camera, palette or realism defaults to the source image.

**Preview compiled prompts** shows the actual text and warnings. Still prompts omit video transitions and character voice direction. An explicit visible-text request removes the conflicting default text/logo exclusion; custom exclusions receive a warning and remain user controlled. Custom templates retain their exact syntax; structured image requirements and warnings remain in handoff metadata/Markdown for manual incorporation.

Choose the Qwen image, FLUX, Midjourney, Runway or general/custom profile under **Create → Generator handoff**. Exact model/version guidance is recorded separately from live capability verification. Qwen-Image-2.1 and its Turbo variant have documented generation/editing guidance; unknown versions remain unverified. Midjourney aspect syntax stays last. No compiler can guarantee typography, identity or artistic quality: inspect real media.

## Configure direct ComfyUI execution

1. Start your existing ComfyUI installation. In ComfyUI, load a workflow that already works with your installed model, then **Export API**. A canvas JSON containing `nodes`/`links` cannot be executed by this adapter. No models, custom nodes or dependencies are installed by Orchestra.
2. Open **Connections**, choose **ComfyUI API workflow**, and set an ID, name and base URL (normally `http://127.0.0.1:8188`). Remote servers require HTTPS; optional bearer credentials stay in local connection storage.
3. Import the API JSON. Import resets mappings for the new graph. In its configuration set `kind` to `image` or `video`, map the inputs, and set the exact file-saving `output_node` ID. Example mapping only:

```json
{
  "kind": "image",
  "workflow": {"REPLACE_WITH_YOUR_EXPORTED_NODE_GRAPH": {}},
  "bindings": {
    "positive": {"node": "6", "input": "text"},
    "negative": {"node": "7", "input": "text"},
    "references": [{"slot": "subject", "node": "10", "input": "image"}]
  },
  "output_node": "9"
}
```

The example is not a runnable model workflow. Use IDs/input names from your own API graph. `positive` is required. Omit `negative` only when the compiled prompt has no native negative conditioning. Reference slots must exactly match the shot handoff; no unrelated image is selected automatically. Remove unused file loader inputs rather than pointing them at arbitrary old server files.

All unmapped values, including checkpoint paths, LoRAs, resolutions, frames, steps, guidance, denoise and seeds, are retained. An optional `seed` binding uses `{"node":"3","input":"seed","value":42}`. Raw configuration text passes to Python without converting full 64-bit seeds into JavaScript numbers. Import does not rewrite workflow numbers.

4. Set the maximum request count, enable and save. **Validate workflow** reads the connected server's node schemas and available model/options; it submits no generation. Validation can become stale if the server changes, so it runs again at execution.
5. Prepare the project's brief/concept and shot prompt normally. Claim its permitted generation task. On the task's **Generate via API** control, choose the matching image/video connection. An MCP agent can use the existing `claim_generation` → `run_provider` → `get_job` flow with its owned job and current workflow acknowledgement.

Orchestra uploads mapped project image references with unique names, submits `/prompt`, saves `remote_prompt_id`, polls its history and downloads only the configured output node's result. That node must yield exactly one PNG/JPEG/WebP image or one MP4. Preview images and other nodes are not chosen automatically. The existing media validator checks the downloaded file; FFprobe is required for video. Results enter the existing workflow review/progression policy.

Runs are serialized per endpoint inside this Orchestra backend. Project dispatch and current inputs are checked again before submission. This is not a global GPU lock against other ComfyUI clients or the legacy companion. Submission attempts count toward the connection limit, including failures during preflight. There are no automatic generation retries. Remote prompt IDs and failures remain in the job. Timeout (about one hour of history polling), shutdown, missing models/nodes, remote execution errors and ambiguous output are never reported as successful generation. A timed-out/interrupted remote prompt may still run: inspect ComfyUI history before retrying. Orchestra does not interrupt the shared server, and running jobs cannot be canceled through this initial adapter.

## Qwen-Image 2.1, MiniMax H3 and other models

Use a working native workflow for the exact model/version; choose its prompt profile independently of the execution connection. Qwen 2.1 supports image generation/editing and RGBA with the corresponding workflow. Turbo and base sampling schedules differ: Orchestra preserves the imported settings. Transparency wording alone cannot enable an alpha-capable pipeline.

For MiniMax H3, use a T2V or I2V workflow configured for the intended dimensions, duration and model. Its prompt profile combines scene, shots, camera and audio intent. Map first/last frame images by their explicit Orchestra slots. Native audio generated into an MP4 is retained. **Video/audio input reference uploads and R2V workflows requiring those files are not supported by this initial connector**; use an external handoff for them. Future models can use Custom prompt profiles plus imported mapped workflows without another fixed node-ID adapter; availability still depends on the installed nodes/models.

Official references, checked 24 October 2026:

- [Qwen-Image-2.1 model repository](https://github.com/QwenLM/Qwen-Image-2.1)
- [ComfyUI Qwen-Image 2.1 announcement and native templates](https://blog.comfy.org/p/qwen-image-21-in-comfyui-open-weight)
- [ComfyUI MiniMax H3 workflows](https://github.com/Comfy-Org/docs/blob/main/tutorials/video/minimax/minimax-h3-native.mdx)

## Portable workflow export

Under **Generator handoff → ComfyUI workflow handoff**, load saved connections and prepare a ZIP. It contains per-shot API workflows, a manifest, actual available image references and instructions for loading those files under their mapped names. It omits the connection URL and bearer key. Review imported graph literals before sharing: custom workflows can contain private information themselves. A package is a revision snapshot and grants no permission to bypass current project gates.

## Verification boundary

Tests exercise image requirements and prompt isolation, exact text/Unicode, uint64 configuration preservation, schema/model/mapping errors, remote error/timeout handling, output-node selection, image/MP4 downloading, authorization rechecks, a local HTTP fixture returning a real validated PNG into Orchestra, portable export and UI controls. These prove connector behavior, not successful inference on your GPU. A live Qwen/H3 generation and the latest rendered browser UI remain pending. No ComfyUI service was listening on port 8188 during this change; automatic approval review blocked launching isolated browser test servers.
