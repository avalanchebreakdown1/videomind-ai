import { test } from "node:test";
import assert from "node:assert/strict";
import { youtubeUrl, requestJson, stageLabel } from "../lib/client.ts";

test("YouTube canonicalization preserves the video ID and rejects unsafe inputs/playlists", () => {
  assert.equal(youtubeUrl("https://youtu.be/fWjsdhR3z3c?t=1"), "https://www.youtube.com/watch?v=fWjsdhR3z3c");
  for (const value of ["https://evil.example/watch?v=fWjsdhR3z3c", "file:///etc/passwd", "https://www.youtube.com/watch?v=fWjsdhR3z3c&list=abc", "https://user@youtube.com/watch?v=fWjsdhR3z3c", "https://youtube.com:80/watch?v=fWjsdhR3z3c"]) assert.throws(() => youtubeUrl(value));
  assert.equal(stageLabel("rewriting_transcript"), "Writing your study notes");
});

test("API client surfaces backend errors and unreadable responses", async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => Response.json({ error: { message: "The local queue is full." } }, { status: 429 });
    await assert.rejects(requestJson("/api/jobs"), /queue is full/);
    globalThis.fetch = async () => new Response("html", { status: 502 });
    await assert.rejects(requestJson("/api/jobs"), /unreadable response/);
    globalThis.fetch = async () => { throw new Error("socket"); };
    await assert.rejects(requestJson("/api/jobs"), /Connection lost/);
  } finally { globalThis.fetch = previous; }
});
