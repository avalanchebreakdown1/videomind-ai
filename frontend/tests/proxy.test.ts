import { test } from "node:test";
import assert from "node:assert/strict";
import { allowedRoute, backendOrigin, mutationAllowed, proxy } from "../lib/proxy.ts";

const id = "00000000-0000-4000-8000-000000000001";
test("Proxy only accepts fixed job routes and a configured loopback destination", () => {
  assert(allowedRoute(`jobs/${id}/document`, "GET"));
  for (const path of ["http://evil.example", "../docs", "jobs/../../etc", `jobs/${id}/unknown`]) assert(!allowedRoute(path, "GET"));
  assert(!allowedRoute("jobs", "DELETE"));
  assert.equal(backendOrigin("http://127.0.0.1:8000"), "http://127.0.0.1:8000");
  for (const value of ["http://evil.example", "http://127.0.0.1/a", "http://user@127.0.0.1", "https://127.0.0.1"]) assert.throws(() => backendOrigin(value));
  assert(!mutationAllowed(new Request("http://localhost:3000/api/jobs", { headers: { origin: "https://evil.example" } })));
  assert(mutationAllowed(new Request("http://localhost:3000/api/jobs", { headers: { origin: "http://localhost:3000" } })));
  assert(mutationAllowed(new Request("http://localhost:3000/api/jobs", { headers: { host: "127.0.0.1:3000", origin: "http://127.0.0.1:3000" } })));
  assert(!mutationAllowed(new Request("http://localhost:3000/api/jobs", { headers: { host: "evil.example", origin: "http://evil.example" } })));
});

test("Proxy rejects cross-origin writes/oversized requests and reports unavailable backend", async () => {
  let response = await proxy(new Request("http://localhost/api/jobs", { method: "POST", headers: { origin: "https://evil.example" } }), "jobs");
  assert.equal(response.status, 403);
  response = await proxy(new Request("http://localhost/api/health", { headers: { host: "evil.example" } }), "health");
  assert.equal(response.status, 403);
  response = await proxy(new Request("http://localhost/api/jobs", { method: "POST", headers: { "content-length": "999999999" } }), "jobs");
  assert.equal(response.status, 413);
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => { throw new Error("ECONNREFUSED secret path"); };
    response = await proxy(new Request("http://localhost/api/health"), "health");
    assert.equal(response.status, 503);
    assert(!(await response.text()).includes("secret"));
  } finally { globalThis.fetch = previous; }
});

test("Proxy preserves download bytes, filename and backend error status", async () => {
  const previous = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response(new Uint8Array([80, 75, 3, 4]), { headers: { "content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "content-disposition": "attachment; filename=notes.docx" } });
    let response = await proxy(new Request(`http://localhost/api/jobs/${id}/document`), `jobs/${id}/document`);
    assert.equal(response.headers.get("content-disposition"), "attachment; filename=notes.docx");
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), new Uint8Array([80, 75, 3, 4]));
    globalThis.fetch = async () => Response.json({ error: { message: "Not ready" } }, { status: 409 });
    response = await proxy(new Request(`http://localhost/api/jobs/${id}/document`), `jobs/${id}/document`);
    assert.equal(response.status, 409);
  } finally { globalThis.fetch = previous; }
});
