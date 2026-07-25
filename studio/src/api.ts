/* The ONLY module that talks to the backend.
 *
 * Every panel goes through here, so the URL shapes, the token and the error
 * handling exist once. A panel that fetches for itself is a panel that will
 * handle a 401 differently from its neighbours.
 */
import type {
  Brief, Bundle, Config, FileView, GraphMap, GraphPath, Health, Neighbourhood,
  NodeView, Project, RepoEntry, ScanReport,
} from "./contracts.js";

/* Same-origin and PREFIX-AWARE: the studio may be mounted under a sub-path
 * behind a reverse proxy (nginx /megabrain/demo/ -> :2137/). Resolving routes
 * against the page's own directory keeps both cases working with no config. */
const BASE = new URL(".", location.href).pathname.replace(/\/$/, "");

/* A tokenised link is all anyone has to share: the token is read once from
 * ?token= and kept, so a reload does not lose it. */
const TOKEN = (() => {
  const fromUrl = new URL(location.href).searchParams.get("token");
  if (fromUrl) localStorage.setItem("mb-token", fromUrl);
  return fromUrl ?? localStorage.getItem("mb-token") ?? "";
})();

export class ApiFailure extends Error {
  constructor(message: string, readonly code: string, readonly status: number) {
    super(message);
  }
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return TOKEN ? { ...extra, Authorization: `Bearer ${TOKEN}` } : extra;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(BASE + path, {
    ...init,
    headers: headers(init?.body ? { "Content-Type": "application/json" } : {}),
  });
  const text = await response.text();
  const parsed: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const failure = parsed as { error?: string; code?: string } | null;
    throw new ApiFailure(failure?.error ?? response.statusText,
                         failure?.code ?? "error", response.status);
  }
  return parsed as T;
}

const query = (params: Record<string, string | undefined>): string => {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
};

export const api = {
  config: () => request<Config>("/config"),
  /* `freshness` hashes every file, so it is asked for explicitly — the right
   * cost for a button, the wrong one for a liveness probe. */
  health: (repo?: string, withFreshness = false) =>
    request<Health>(`/health${query({ repo, freshness: withFreshness ? "1" : undefined })}`),
  repos: () => request<{ repos: RepoEntry[] }>("/repos"),

  /* Per REPO, unlike /config which describes the deployment: the questions a
   * repository authored about itself, and the models it chose. */
  project: (repo?: string) => request<Project>(`/project${query({ repo })}`),

  /* The census: what indexing WOULD read. Free, so it always comes first. */
  scan: (path: string) => request<ScanReport>(`/scan${query({ path })}`),

  search: (q: string, repo?: string, content?: "code" | "docs", rerank?: boolean) =>
    request<Bundle>("/search", {
      method: "POST",
      body: JSON.stringify({ query: q, repo, content, rerank }),
    }),

  /* The mental map for a question: prose written at study time, relations read
   * live from the graph. No model runs here — a 404 `study_not_found` means the
   * repo was never studied, which the view reports as an action, not an error. */
  brief: (q: string, repo?: string, limit?: number, rerank?: boolean) =>
    request<Brief>("/brief", {
      method: "POST",
      body: JSON.stringify({ query: q, repo, limit, rerank }),
    }),

  file: (file: string, repo?: string, symbol?: string) =>
    request<FileView>(`/get${query({ file, repo, symbol })}`),

  graph: (repo?: string) => request<GraphMap>(`/graph${query({ mode: "map", repo })}`),

  node: (node: string, repo?: string) =>
    request<Neighbourhood>(`/graph${query({ mode: "node", node, repo, label: "0" })}`),

  /* The full node view: both edge directions kept per kind, the semantic
   * twins, the symbols. `node` accepts a TERM, not only a path. */
  graphNode: (node: string, repo?: string) =>
    request<NodeView>(`/graph${query({ mode: "node", node, repo })}`),

  /* How two files are connected — with the carrier symbols and the real code
   * at both ends of every hop. */
  graphPath: (source: string, target: string, repo?: string) =>
    request<GraphPath>(`/graph${query({ mode: "path", source, target, repo })}`),

  /* Both streams are POST + SSE, so EventSource (GET-only) cannot be used:
   * the body stream is read and the `event:`/`data:` frames parsed here. */
  ask(question: string, repo: string | undefined,
      content: "code" | "docs" | undefined,
      onEvent: (event: string, data: unknown) => void): {
    done: Promise<void>; abort: () => void;
  } {
    return stream("/ask/stream", { question, repo, content }, onEvent);
  },

  /* `llm` also writes the mental map — a model call per changed file, which is
   * why it is a parameter the caller has to pass rather than a default. */
  index(repo: string, llm: boolean,
        onEvent: (event: string, data: unknown) => void): {
    done: Promise<void>; abort: () => void;
  } {
    return stream("/index/stream", { path: repo, llm }, onEvent);
  },
};

function stream(path: string, body: object,
                onEvent: (event: string, data: unknown) => void): {
  done: Promise<void>; abort: () => void;
} {
  const controller = new AbortController();
  const done = (async () => {
    const response = await fetch(BASE + path, {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      const failed = (await response.json().catch(() => null)) as { error?: string; code?: string } | null;
      throw new ApiFailure(failed?.error ?? "stream failed", failed?.code ?? "error",
                           response.status);
    }
    await readFrames(response.body, onEvent);
  })();
  return { done, abort: () => controller.abort() };
}

async function readFrames(body: ReadableStream<Uint8Array>,
                          onEvent: (event: string, data: unknown) => void): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffered += decoder.decode(value, { stream: true });
    let split: number;
    // A frame ENDS at the blank line; anything before that is a partial read,
    // which is the normal case for a chunked stream.
    while ((split = buffered.indexOf("\n\n")) >= 0) {
      const frame = buffered.slice(0, split);
      buffered = buffered.slice(split + 2);
      let name = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) onEvent(name, JSON.parse(data) as unknown);
    }
  }
}
