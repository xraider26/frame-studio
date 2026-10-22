# Your first project

Frame Studio organizes a video production. Your agent and chosen generators create the media; your editor assembles the final cut. You can review and adjust each creative decision along the way.

## 1. Open the studio

Install the [Windows beta](https://github.com/xraider26/frame-studio/releases/tag/v0.2.0-beta.1), then launch **Frame Studio**. It bundles its runtimes. See [Windows setup](WINDOWS.md) for data, logs and source builds.

Choose **New project**, give it a name and select a content recipe. Explore **Template library** first if you want to compare formats and their example images. Start with one short project before creating a large production batch.

## 2. Describe the result you want

Record the audience, intended emotion, runtime, aspect ratio and viewer promise. Decide what the opening sets up and what the ending pays off. Include factual sources for claims when relevant.

If using an agent, open **Connections & MCP**, select your client format and copy the configuration generated on your machine into that client's MCP settings. Keep the studio open. The desktop menu also copies the JSON configuration. No developer drive or username needs to be copied.

An example instruction for your agent:

> Use Frame Studio to prepare a 30-second short drama about a ceramic artist repairing a gift before a visitor arrives. Start with the short-drama recipe. Propose the brief and script, prepare a coherent shot plan and explain how the camera and lighting support the emotional turn. Follow the project's approval policy. Use only my authorized generation tools, return actual outputs and stop when approval is required.

MCP gives the agent a workflow, not a built-in image/video model. Confirm that your agent can actually use the generator you intend before requesting media.

## 3. Set review gates

Open **Workflow & approvals**. Require approval on the steps you want to inspect; permit automatic progression where appropriate. The agent reads those requirements from the project. It must stop at an approval gate.

For your first project, inspect the brief, shot direction and representative pilot before continuing. You can adjust the policy yourself. Agent evidence does not count as your human approval.

## 4. Shape the look

Open **Camera & visual library** to explore camera treatments, lens/depth cues, framing, angles, lighting and movement. Compare related examples, read their use/tradeoff notes and apply a chosen technique explicitly.

**Apply to shot** changes the fields shown in the preview for the selected shot. **Apply as project defaults** changes inherited direction; explicit shot overrides still take precedence. You can also set custom values under **Shots & direction** and use its (?) examples. Basic/Professional changes the amount of visible detail, not the underlying standards.

Prepare character, location and prop references in the production bible. Check wardrobe, mutable scene states and physical light positions across cuts. The example gallery is a teaching aid; it is not silently attached as your project's generation references.

## 5. Generate through your chosen route

- **MCP agent:** let your agent claim the next permitted task, generate through an authorized tool and return the real image or MP4. It should refresh project state after changes and follow the next action.
- **External handoff:** open **Generator handoff**, choose the prompt profile for the tool you will use and export the ZIP. Give that package to your generator/agent and return the resulting files to the studio workflow.
- **API adapter:** configure a connection implementing the studio's JSON Job API. A vendor key alone does not make an arbitrary provider endpoint compatible; see the [adapter contract](MCP.md#api-based-generators).

A prompt profile adapts instructions. It does not log into Google Flow or another service. Account access, generator support and charges are managed through the tools you connect.

## 6. Inspect, revise and finish

Review returned takes against their required checks. Check the full clip, including its beginning, middle and end. A good-looking frame alone does not prove the motion, audio or story works.

Name a specific defect when asking for a revision. Select compatible takes and use **Editor handoff** to export the chosen media and timing/sound notes. Assemble the cut in your preferred editor, import the actual final video and review the export.

The **Video trials** view records human assessments of real finished outputs, including failed trials. It does not automatically certify a template's quality.

## 7. Save what worked

In **Template library**, save the useful creative settings, workflow policy and optional shot plan as a named template. Record what worked, the model/settings and any limitations. Reference file bindings and generated takes need their own project handling; a saved template does not transfer completed approvals or spending history.

When the format works for more than one idea, use **Production queue** to organize episodes, variations or a campaign. Each item is a real independent project that still needs planning, generation and review. A batch count is not a promise of parallel generator capacity or successful videos.

## FAQ

**Will the app make a finished video from an idea on its own?**  
It can coordinate that work with a capable connected agent and generators. It does not include an internal script-writing/generation model or timeline renderer. Your editor handles assembly.

**Can I use it without a generation API?**  
Yes. Use generator-specific exports or an agent with its own tools. Those tools may have their own access requirements and charges.

**Does it require a particular GPU?**  
The production workspace is not tied to the original developer's GPU. Any local generation model has separate hardware requirements.

**Where are my projects?**  
In the desktop app, use **Frame Studio → Open data folder**. Data normally lives under `%APPDATA%\Frame Studio\studio_data`. A source checkout uses its local `studio_data` directory. These are separate workspaces; the installer does not silently migrate repository data.

**Can everyone use the same MCP configuration?**  
The structure is shared, but the executable/data paths are generated for each installation. Copy them from your own studio. Reconnect the client after changing its MCP settings.

**Do templates guarantee consistent characters or professional results?**  
They preserve direction, reference requirements and review standards. Actual consistency depends on the generator, references, execution and inspection. Test a representative pilot and record real results.

**Why can't I download the release?**  
Use the [Windows beta release page](https://github.com/xraider26/frame-studio/releases/tag/v0.2.0-beta.1) and expand its Assets section. The beta is marked as a prerelease, so a generic “latest stable release” link may not find it. The public download does not require repository membership.

**What should I include in a bug report?**  
App version, desktop versus source mode, Windows version, exact steps and the expected/actual result. Use a small synthetic project where possible. Review logs for credentials/private content before attaching them. See [security reporting](../SECURITY.md).
