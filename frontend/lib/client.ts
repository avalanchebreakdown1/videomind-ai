export interface Job {
  id: string; state: "queued" | "running" | "completed" | "failed" | "cancelled";
  stage: string; progress: number; cancel_requested: boolean; artifacts: string[];
  metadata: { title?: string; filename?: string; duration_seconds?: number };
  error: { code: string; message: string } | null;
  document: { quality_state: string; findings: number } | null;
}
export interface Notes {
  title: string;
  sections: { heading: string; blocks?: { kind: string; text: string }[]; paragraphs?: { text: string }[] }[];
}

export function youtubeUrl(raw: string): string {
  let url: URL;
  try { url = new URL(raw.trim()); } catch { throw new Error("Enter a valid YouTube video URL."); }
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.port || url.hash) throw new Error("Enter a single YouTube video URL.");
  if (url.searchParams.has("list") || url.searchParams.has("index")) throw new Error("Use a single video URL without playlist parameters.");
  let id: string | null = null;
  if (["youtu.be", "www.youtu.be"].includes(url.hostname)) id = url.pathname.match(/^\/([\w-]{11})\/?$/)?.[1] || null;
  if (["youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"].includes(url.hostname)) {
    id = url.pathname === "/watch" && url.searchParams.getAll("v").length === 1 ? url.searchParams.get("v") :
      url.pathname.match(/^\/(?:shorts|embed)\/([\w-]{11})\/?$/)?.[1] || null;
  }
  if (!id || !/^[\w-]{11}$/.test(id)) throw new Error("Use a YouTube watch, Shorts, or youtu.be link to one video.");
  return `https://www.youtube.com/watch?v=${id}`;
}

export async function requestJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(url, { ...options, cache: "no-store" }); }
  catch { throw new Error("Connection lost. Check your connection and try again."); }
  let data;
  try { data = await response.json(); } catch { throw new Error("The service returned an unreadable response. Please try again."); }
  if (!response.ok) throw new Error(data?.error?.message || `The request failed (${response.status}).`);
  return data as T;
}

export const terminal = (job: Job) => ["completed", "failed", "cancelled"].includes(job.state);
export function stageLabel(stage: string): string {
  return ({ queued: "Waiting in the local queue", ingesting: "Retrieving audio", created: "Preparing audio", normalizing: "Preparing audio",
    transcribing: "Transcribing your video", stitching: "Assembling the transcript", transcription_completed: "Transcript ready", rewriting_transcript: "Writing your study notes",
    exporting_docx: "Formatting your document", completed: "Your notes are ready", failed: "Processing stopped", cancelled: "Processing cancelled",
    interrupted: "Processing interrupted", document_completed: "Finishing your document" } as Record<string, string>)[stage] || "Processing your source";
}
