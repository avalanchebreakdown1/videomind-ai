import { test, expect, type Page, type TestInfo } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function inspectJob(page: Page, info: TestInfo) {
  const created = page.waitForResponse(r => r.url().endsWith("/api/jobs") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Create my notes" }).click();
  const submitted = await created;
  expect(submitted.status()).toBe(202);
  const { id } = await submitted.json();
  console.log(`Real job: ${id}`);
  let result: { state: string; stage: string; error?: unknown } = { state: "queued", stage: "queued" };
  let previous = "";
  const deadline = Date.now() + 85 * 60 * 1000;
  while (Date.now() < deadline) {
    const response = await page.request.get(`/api/jobs/${id}`);
    expect(response.ok()).toBeTruthy();
    result = await response.json();
    if (result.stage !== previous) { console.log(`Real job ${id}: ${result.stage}`); previous = result.stage; }
    if (["completed", "failed", "cancelled"].includes(result.state)) break;
    await page.waitForTimeout(5000);
  }
  await info.attach("real-job-result", { body: JSON.stringify({ id, ...result }), contentType: "application/json" });
  expect(result.state, JSON.stringify(result)).toBe("completed");
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible();
  await expect(page.getByRole("tabpanel", { name: "Study notes preview" })).not.toBeEmpty();
  for (const name of ["Download Word", "Notes TXT", "Transcript TXT"]) {
    const pending = page.waitForEvent("download");
    await page.getByRole("button", { name, exact: true }).click();
    const download = await pending;
    const target = info.outputPath(download.suggestedFilename());
    await download.saveAs(target);
    const bytes = await readFile(target);
    expect(bytes.length).toBeGreaterThan(100);
    if (name === "Download Word") expect(bytes.subarray(0, 2).toString()).toBe("PK");
  }
  await page.reload();
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible();
}

test("authorized real YouTube → ASR → automatic document → browser downloads", async ({ page }, info) => {
  const url = process.env.VIDEOMIND_REAL_VIDEO_URL;
  test.skip(!url, "Set VIDEOMIND_REAL_VIDEO_URL only for a video you are authorized to process.");
  await page.goto("/");
  await expect(page.getByText("Ready to process")).toBeVisible();
  await page.getByLabel("YouTube video URL").fill(url!);
  await page.getByLabel("I have permission").check();
  await inspectJob(page, info);
});

test("authorized real long audio → ASR → automatic document → browser downloads", async ({ page }, info) => {
  const path = process.env.VIDEOMIND_REAL_AUDIO_PATH;
  test.skip(!path, "Set VIDEOMIND_REAL_AUDIO_PATH only for existing authorized local audio.");
  await page.goto("/");
  await expect(page.getByText("Ready to process")).toBeVisible();
  await page.getByRole("tab", { name: "Audio file" }).click();
  await page.getByLabel("Audio recording").setInputFiles(path!);
  await page.getByLabel("I have permission").check();
  await inspectJob(page, info);
});
