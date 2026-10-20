import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

async function ready(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByText("Ready to process")).toBeVisible();
}
async function submitVideo(page: import("@playwright/test").Page, id = "fWjsdhR3z3c") {
  await page.getByLabel("YouTube video URL").fill(`https://www.youtube.com/watch?v=${id}`);
  await page.getByLabel("I have permission").check();
  await page.getByRole("button", { name: "Create my notes" }).click();
}

test("real Next proxy → FastAPI job → previews and DOCX/TXT downloads; resumes after refresh", async ({ page }) => {
  const errors: string[] = []; page.on("pageerror", e => errors.push(e.message));
  await ready(page); await submitVideo(page);
  await expect(page.getByRole("progressbar")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible({ timeout: 30000 });
  await expect(page.getByRole("tabpanel", { name: "Study notes preview" })).toContainText("Optical measurements");
  await page.getByRole("tab", { name: "Transcript", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Transcript preview" })).toContainText(".5 mW over 2 cm²");
  for (const name of ["Download Word", "Notes TXT", "Transcript TXT"]) {
    const pending = page.waitForEvent("download");
    await page.getByRole("button", { name, exact: true }).click();
    const download = await pending;
    const bytes = await readFile((await download.path())!);
    if (name === "Download Word") { expect(download.suggestedFilename()).toMatch(/\.docx$/); expect(bytes.subarray(0, 2).toString()).toBe("PK"); }
    else { expect(download.suggestedFilename()).toMatch(/\.txt$/); expect(bytes.toString()).toContain(".5 mW"); }
  }
  await page.reload();
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible();
  await expect(page.getByRole("tabpanel", { name: "Study notes preview" })).toContainText("Optical measurements");
  const link = page.url();
  await page.evaluate(() => localStorage.clear());
  await page.goto(link);
  await expect(page.getByRole("tabpanel", { name: "Study notes preview" })).toContainText("Optical measurements");
  expect(errors).toEqual([]);
});

test("client validation and actual download failure are actionable", async ({ page }) => {
  await ready(page);
  await page.getByLabel("YouTube video URL").fill("https://example.com/video");
  await page.getByRole("button", { name: "Create my notes" }).click();
  await expect(page.locator('main [role="alert"]')).toContainText("permission");
  await page.getByLabel("I have permission").check();
  await page.getByRole("button", { name: "Create my notes" }).click();
  await expect(page.locator('main [role="alert"]')).toContainText("YouTube");
  await submitVideo(page, "AAAAAAAAAAA");
  await expect(page.locator('main [role="alert"]')).toContainText("unavailable");
  await expect(page.getByRole("button", { name: "Download Word" })).toHaveCount(0);
});

test("writing failure preserves a downloadable transcript through the real API", async ({ page }) => {
  await ready(page); await page.getByRole("tab", { name: "Audio file" }).click();
  const wav = Buffer.alloc(44 + 32000);
  wav.write("RIFF", 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write("WAVEfmt ", 8); wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write("data", 36); wav.writeUInt32LE(32000, 40);
  await page.getByLabel("Audio recording", { exact: true }).setInputFiles({ name: "document-failure.wav", mimeType: "audio/wav", buffer: wav });
  await page.getByLabel("I have permission").check(); await page.getByRole("button", { name: "Create my notes" }).click();
  await expect(page.locator('main [role="alert"]')).toContainText("Document generation failed", { timeout: 30000 });
  await page.getByRole("tab", { name: "Transcript", exact: true }).click();
  await expect(page.getByRole("tabpanel", { name: "Transcript preview" })).toContainText(".5 mW");
  await expect(page.getByRole("button", { name: "Transcript TXT" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Download Word" })).toHaveCount(0);
});

test("mobile layout fits the viewport and previews work", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await ready(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await submitVideo(page);
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible({ timeout: 30000 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByRole("button", { name: "Download Word" })).toBeVisible();
});

test("cancellation and same-origin proxy restrictions", async ({ page, request }) => {
  await ready(page); await submitVideo(page);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Processing cancelled" })).toBeVisible({ timeout: 30000 });
  expect((await request.post("/api/jobs", { headers: { Origin: "https://evil.example" } })).status()).toBe(403);
  expect((await request.get("/api/anything-else")).status()).toBe(404);
});

test("service outage message and recovery without page reload", async ({ page }) => {
  await page.route("**/api/health", route => route.fulfill({ status: 503, json: { error: { message: "Unavailable" } } }));
  await page.goto("/");
  await expect(page.getByText("Service unavailable", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Create my notes" })).toBeDisabled();
  await page.unroute("**/api/health");
  await expect(page.getByText("Ready to process")).toBeVisible({ timeout: 20000 });
});


test("successful audio upload preserves literal text safely in the preview", async ({ page }) => {
  await ready(page); await page.getByRole("tab", { name: "Audio file" }).click();
  const wav = Buffer.alloc(44 + 32000);
  wav.write("RIFF", 0); wav.writeUInt32LE(wav.length - 8, 4); wav.write("WAVEfmt ", 8); wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20); wav.writeUInt16LE(1, 22); wav.writeUInt32LE(8000, 24); wav.writeUInt32LE(16000, 28);
  wav.writeUInt16LE(2, 32); wav.writeUInt16LE(16, 34); wav.write("data", 36); wav.writeUInt32LE(32000, 40);
  await page.getByLabel("Audio recording", { exact: true }).setInputFiles({ name: "<img onerror=alert(1)>.wav", mimeType: "audio/wav", buffer: wav });
  await page.getByLabel("I have permission").check(); await page.getByRole("button", { name: "Create my notes" }).click();
  await expect(page.getByRole("heading", { name: "Your notes are ready" })).toBeVisible({ timeout: 30000 });
  await expect(page.locator("article img")).toHaveCount(0);
  await expect(page.getByRole("tabpanel", { name: "Study notes preview" })).toContainText("<img onerror=alert(1)>.wav");
  await expect(page.getByRole("button", { name: "Download Word" })).toBeVisible();
});
