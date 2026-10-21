async (page) => {
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const assert = (value, message) => { if (!value) throw new Error(message); };
  await page.goto('http://127.0.0.1:3000/studio');
  await page.getByText('Local studio connected', { exact: true }).waitFor();
  const choices = await page.locator('#project-select option').filter({hasText:'MCP roundtrip · verification fixture'}).all();
  assert(choices.length > 0, 'MCP-created fixture is missing from the browser');
  const id = await choices[0].getAttribute('value');
  await page.getByLabel('Project', { exact: true }).selectOption(id);
  await page.getByRole('heading', { name: 'MCP roundtrip · verification fixture', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Workflow & approvals', exact: true }).click();
  await page.getByRole('button', { name: 'Approve this step' }).waitFor();
  const image = page.locator('.fs-media-strip img').first();
  await image.waitFor();
  await page.waitForFunction(() => { const img = document.querySelector('.fs-media-strip img'); return img && img.complete && img.naturalWidth === 320; });
  assert(await image.evaluate(img => img.complete && img.naturalWidth === 320), 'Returned image did not render');
  await page.screenshot({ path: '../output/playwright/studio-review.png', fullPage: true });

  // Project operations exercise actual UI mutations; original stays intact.
  await page.getByTitle('Duplicate project', { exact: true }).click();
  const duplicateDialog = page.getByRole('dialog', { name: 'Duplicate project' });
  await duplicateDialog.getByLabel('New project name').fill('Browser verification copy');
  await duplicateDialog.getByRole('button', { name: 'Duplicate project', exact: true }).click();
  await page.getByRole('heading', { name: 'Browser verification copy', exact: true }).waitFor();
  const cloneId = await page.getByLabel('Project', { exact: true }).inputValue();
  assert(cloneId !== id, 'Duplicate kept original project ID');
  await page.getByTitle('Delete project', { exact: true }).click();
  await page.getByRole('button', { name: 'Move to Trash', exact: true }).click();
  await page.getByRole('heading', { name: 'Create with a plan.', exact: true }).waitFor();
  assert(await page.locator(`#project-select option[value="${cloneId}"]`).count() === 0, 'Deleted project still active');
  await page.getByTitle('Open Trash', { exact: true }).click();
  const trash = page.getByRole('dialog', { name: 'Project Trash' });
  await trash.getByText('Browser verification copy', { exact: true }).waitFor();
  await trash.getByRole('button', { name: 'Restore project', exact: true }).click();
  await trash.getByText('Trash is empty.', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Close project actions' }).click();
  await page.getByLabel('Project', { exact: true }).selectOption(cloneId);
  await page.getByRole('heading', { name: 'Browser verification copy', exact: true }).waitFor();

  // Generator choice changes real exported prompts and produces a downloadable file.
  await page.getByRole('button', { name: 'Generator handoff', exact: true }).click();
  await page.getByLabel('Video generator template').selectOption('runway_i2v');
  await page.getByRole('button', { name: 'Apply generator choices', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Generator choices saved' }).waitFor();
  await page.getByRole('button', { name: 'Prepare export package', exact: true }).click();
  const downloadLink = page.getByRole('link', { name: 'Download handoff ZIP', exact: true });
  await downloadLink.waitFor();
  const downloaded = page.waitForEvent('download');
  await downloadLink.click();
  const file = await downloaded;
  await file.saveAs('../output/playwright/studio-generator-handoff.zip');
  const prompts = await page.getByLabel('Generator-specific exported prompts').inputValue();
  assert(prompts.includes('runway_i2v') && prompts.includes('Camera movement:'), 'Generator-specific prompt profile not applied');
  await page.screenshot({ path: '../output/playwright/studio-generator-export.png', fullPage: true });

  // Simultaneous settings and shot drafts must survive independent saves.
  await page.getByRole('button', { name: 'Shots & direction', exact: true }).click();
  await page.getByLabel('Lens', { exact: true }).fill('50mm');
  await page.getByLabel('Shot 1 title', { exact: true }).fill('A revised observatory');
  await page.getByRole('button', { name: 'Apply creative settings', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Creative plan applied' }).waitFor();
  assert(await page.getByLabel('Shot 1 title', { exact: true }).inputValue() === 'A revised observatory', 'Saving settings lost shot draft');
  await page.getByRole('button', { name: 'Apply shot plan', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Creative plan applied' }).waitFor();
  await page.reload();
  await page.getByText('Local studio connected', { exact: true }).waitFor();
  await page.getByLabel('Project', { exact: true }).selectOption(cloneId);
  await page.getByRole('button', { name: 'Shots & direction', exact: true }).click();
  assert(await page.getByLabel('Shot 1 title', { exact: true }).inputValue() === 'A revised observatory', 'Shot did not persist after reload');
  assert(await page.getByLabel('Lens', { exact: true }).inputValue() === '50mm', 'Settings did not persist after reload');

  // The user's checkbox controls auto/manual progression and persists.
  await page.getByRole('button', { name: 'Workflow & approvals', exact: true }).click();
  await page.getByLabel('Approval required for Brief', { exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Approval policy saved' }).waitFor();
  await page.reload();
  await page.getByText('Local studio connected', { exact: true }).waitFor();
  await page.getByLabel('Project', { exact: true }).selectOption(cloneId);
  await page.getByRole('button', { name: 'Workflow & approvals', exact: true }).click();
  assert(!(await page.getByLabel('Approval required for Brief', { exact: true }).isChecked()), 'Approval toggle did not persist');

  // A concurrent agent edit cannot cause approval of an unseen or unsaved document.
  await page.locator('.fs-stage-row').filter({ hasText: 'Script' }).getByRole('button').click();
  await page.getByLabel('Step document', { exact: true }).fill('Unsaved browser draft');
  await page.evaluate(async (projectId) => {
    const cmd = async (operation, args = {}) => { const r = await fetch('/api/studio/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation, arguments: args }) }); return r.json(); };
    const p = await cmd('get_project', { project_id: projectId });
    await cmd('complete_step', { project_id: projectId, step: 'script', output: { text: 'A different script returned by an agent.' }, expected_revision: p.revision });
  }, cloneId);
  await page.waitForTimeout(4500);
  assert(await page.getByLabel('Step document', { exact: true }).inputValue() === 'Unsaved browser draft', 'Polling discarded a dirty document');
  assert(!(await page.getByRole('button', { name: 'Approve this step' }).isEnabled()), 'Approval enabled over an unsaved document');
  await page.getByRole('button', { name: 'Save & complete step', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Project changed' }).waitFor();

  // Responsive layout checks cover operational surfaces, not just the empty page.
  await page.getByRole('button', { name: 'Project home', exact: true }).click();
  for (const width of [1280, 1024, 375, 320]) {
    await page.setViewportSize({ width, height: 900 });
    const over = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    assert(!over, `Project home overflows at ${width}`);
  }
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.getByRole('button', { name: 'Connections & MCP', exact: true }).click();
  await page.getByRole('heading', { name: 'Your agent runs the workflow.', exact: true }).waitFor();
  await page.screenshot({ path: '../output/playwright/studio-mcp-connections.png', fullPage: true });
  assert(errors.length === 0, errors.join('\n'));
  return ('PASS: MCP project visible in connected browser; real thumbnail; duplicate/delete/trash/restore; generator-specific downloadable ZIP; independent shot/settings drafts; approval policy persistence; stale document protection; project home at 1280/1024/375/320; no runtime errors.');
}
