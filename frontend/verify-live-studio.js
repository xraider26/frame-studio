async (page) => {
 await page.goto('http://127.0.0.1:3000/studio');
 await page.getByText('Local studio connected',{exact:true}).waitFor();
 await page.getByRole('heading',{name:'Create with a plan.',exact:true}).waitFor();
 await page.screenshot({path:'../output/playwright/studio-live.png',fullPage:true});
 return {title:await page.title(),templates:await page.locator('.fs-template').count(),projects:await page.locator('#project-select option:not([disabled])').count(),status:'Live app is connected to the production local workspace; QA fixtures are separate.'};
}
