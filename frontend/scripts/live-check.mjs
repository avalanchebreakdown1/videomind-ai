import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const url = process.env.VIDEOMIND_LIVE_URL;
if (!url) throw new Error('Set VIDEOMIND_LIVE_URL to an authorized video URL.');
const folder = path.resolve(process.env.VIDEOMIND_LIVE_REPORT_DIR || `../runs/frontend-live-${Date.now()}`);
await mkdir(folder, { recursive: false });
const browser = await chromium.launch();
const page = await browser.newPage({ baseURL: 'http://127.0.0.1:3000', viewport: { width: 1440, height: 1080 } });
const browserErrors = [];
page.on('pageerror', error => browserErrors.push(error.message));
try {
  await page.goto('http://127.0.0.1:3000');
  await page.getByText('Ready to process').waitFor();
  await page.screenshot({ path: path.join(folder, 'desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  if (!(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))) throw new Error('Mobile overflow');
  await page.screenshot({ path: path.join(folder, 'mobile.png'), fullPage: true });
  await page.setViewportSize({ width: 1440, height: 1080 });
  let submitted;
  if (process.env.VIDEOMIND_LIVE_JOB_ID) {
    const id = process.env.VIDEOMIND_LIVE_JOB_ID;
    const response = await page.request.get(`/api/jobs/${id}`);
    if (!response.ok()) throw new Error(await response.text());
    submitted = await response.json();
    await page.evaluate(id => localStorage.setItem('videomind-recent-jobs', JSON.stringify([{ id, title: 'Live video test' }])), id);
    await page.reload();
  } else {
    await page.getByLabel('YouTube video URL').fill(url);
    await page.getByLabel('I have permission').check();
    const accepted = page.waitForResponse(r => r.url().endsWith('/api/jobs') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Create my notes' }).click();
    const response = await accepted;
    if (response.status() !== 202) throw new Error(await response.text());
    submitted = await response.json();
  }
  await writeFile(path.join(folder, 'submitted.json'), JSON.stringify(submitted, null, 2));
  console.log('Live job:', submitted.id);
  let job;
  const deadline = Date.now() + 900000;
  let last = '';
  while (Date.now() < deadline) {
    const status = await page.request.get(`/api/jobs/${submitted.id}`);
    job = await status.json();
    const current = `${job.stage}: ${job.progress}%`;
    if (current !== last) { console.log(current); last = current; }
    if (['completed', 'failed', 'cancelled'].includes(job.state)) break;
    await page.waitForTimeout(3000);
  }
  if (job?.state !== 'completed') throw new Error(JSON.stringify(job));
  await page.getByRole('heading', { name: 'Your notes are ready' }).waitFor();
  await page.getByRole('tabpanel', { name: 'Study notes preview' }).getByRole('heading').first().waitFor();
  const preview = await page.getByRole('tabpanel', { name: 'Study notes preview' }).innerText();
  if (!/\bpass\b/i.test(preview)) throw new Error('Taught pass statement missing');
  if (/names must be unique/i.test(preview)) throw new Error('Known scope regression');
  for (const [label, filename] of [['Download Word', 'document.docx'], ['Notes TXT', 'document.txt'], ['Transcript TXT', 'transcript.txt']]) {
    const pending = page.waitForEvent('download');
    await page.getByRole('button', { name: label, exact: true }).click();
    await (await pending).saveAs(path.join(folder, filename));
  }
  await page.screenshot({ path: path.join(folder, 'completed.png'), fullPage: true });
  await page.getByRole('tab', { name: 'Transcript', exact: true }).click();
  const transcript = await page.getByRole('tabpanel', { name: 'Transcript preview' }).innerText();
  if (transcript.length < 100) throw new Error('Missing transcript');
  await page.reload();
  await page.getByRole('heading', { name: 'Your notes are ready' }).waitFor();
  await writeFile(path.join(folder, 'report.json'), JSON.stringify({ job, browserErrors, previewCharacters: preview.length, transcriptCharacters: transcript.length, refreshRecovery: true, mobileOverflow: false, downloads: ['docx','notes_txt','transcript_txt'] }, null, 2));
  if (browserErrors.length) throw new Error(JSON.stringify(browserErrors));
  console.log('Live browser workflow passed. Artifacts:', folder);
} finally { await browser.close(); }
