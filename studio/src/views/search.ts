/* The search view: a query bar, then CORE as expandable file cards and
 * RELATED as a compact map.
 *
 * The card is closed by default and opens on click. That is the design's
 * answer to the same measurement the renderer makes: RELATED holds 45% of the
 * gold files but ~95% of its volume is code nobody asked for, so the code is
 * one click away rather than on screen.
 */
import { api } from "../api.js";
import type { Bundle, Tier1File, Tier2File } from "../contracts.js";
import { code, el, fill } from "../dom.js";
import { icon } from "../icons.js";
import { scopePicker } from "../scope.js";
import { suggestionStrip } from "../suggestions.js";

export interface SearchView {
  /* Re-read anything per-repo — called when the selection changes. */
  refresh(): void;
  root: HTMLElement;
  focus(): void;
}

export function searchView(repo: () => string | undefined,
                           onOpen: (file: string) => void,
                           onError: (failure: unknown) => void): SearchView {
  const input = el("input", {
    class: "query-input", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder: "how does the SSE decoder feed the typed event stream?",
  }) as HTMLInputElement;
  const results = el("div", {});
  const stats = el("div", { class: "stats-row" });
  /* CODE or DOCS, never a blend — the engine's own rule, surfaced. With both
   * indexed, a long README wins on prose-shaped questions and buries the
   * implementation it describes, so the choice is explicit rather than
   * guessed from the wording. "Both" stays the default: it is the honest
   * answer when nobody has said which they want. */
  const scope = scopePicker();

  const run = async (): Promise<void> => {
    if (!input.value.trim()) return;
    fill(results, el("div", { class: "empty" }, el("div", { class: "spinner" }),
                     "searching…"));
    try {
      render(await api.search(input.value.trim(), repo(), scope.value()),
             results, stats, onOpen);
    } catch (failure) {
      onError(failure);
    }
  };
  input.addEventListener("keydown", (event) => {
    if ((event as KeyboardEvent).key === "Enter") void run();
  });
  const go = el("button", { class: "badge" }, icon("spark", 13), "SEARCH");
  go.addEventListener("click", () => void run());

  const suggestions = suggestionStrip(repo, (question) => {
    input.value = question; void run();
  });

  return {
    root: el("div", { class: "view-wrap" },
      el("div", { class: "query-wrap" },
        el("div", { class: "query-icon" }, icon("search")), input, scope.root, go),
      suggestions.root, stats, results),
    focus: () => input.focus(),
    refresh: () => suggestions.reload(),
  };
}

/* The honesty banner. Silent on "strong": a banner on every answer is a
 * banner on none. On "none" it names what the list below actually is —
 * nearest vocabulary, not an answer — because the cards underneath will still
 * render fluent summaries of each file, and without this line those summaries
 * read as an endorsement. */
function evidenceBanner(bundle: Bundle): HTMLElement[] {
  if (bundle.evidence === "weak") {
    return [el("div", { class: "info-bar warn" },
      el("b", {}, "thin evidence"),
      ` — the closest match is weak (top cosine ${bundle.top_cosine.toFixed(2)}). `
      + "Verify before relying on it.")];
  }
  if (bundle.evidence === "none") {
    return [el("div", { class: "warn-bar" },
      el("b", {}, "nothing in this repo clearly answers this"),
      ` (top cosine ${bundle.top_cosine.toFixed(2)}). The files below merely `
      + "share vocabulary with the question.")];
  }
  return [];
}

function render(bundle: Bundle, results: HTMLElement, stats: HTMLElement,
                onOpen: (file: string) => void): void {
  fill(stats, el("b", {}, String(bundle.tier1.length)), " core files",
       el("div", { class: "sdot" }), el("b", {}, String(bundle.tier2.length)),
       " related", el("div", { class: "sdot" }), el("b", {}, `${bundle.ms}ms`),
       el("div", { class: "sdot" }), bundle.repo);
  fill(results,
    ...evidenceBanner(bundle),
    sectionHead("CORE", "full code"),
    ...bundle.tier1.map((file) => coreCard(file, onOpen)),
    ...(bundle.tier2.length
      ? [sectionHead("RELATED", "the map — click to open"),
         el("div", { class: "split-2" },
            ...bundle.tier2.map((file) => relatedCard(file, onOpen)))]
      : []));
}

function sectionHead(label: string, note: string): HTMLElement {
  return el("div", { class: "section-head" },
    el("div", { class: "section-label" }, label),
    el("div", { class: "section-rule" }),
    el("div", { style: "font-size:11px;color:var(--muted)" }, note));
}

function coreCard(file: Tier1File, onOpen: (file: string) => void): HTMLElement {
  const body = el("div", { style: "padding:0 16px 14px;display:grid;gap:10px" });
  for (const chunk of file.chunks) {
    body.append(el("div", { class: "chunk" },
      el("div", { style: "padding:8px 12px;display:flex;gap:10px;align-items:center" },
        el("span", { class: "kind-pill on" }, chunk.kind),
        el("span", { class: "mono", style: "font-size:11.5px" },
           chunk.name ?? file.file),
        el("span", { class: "mono", style: "font-size:10.5px;color:var(--muted)" },
           `L${chunk.start_line}-${chunk.end_line}`)),
      code(chunk.text, chunk.start_line)));
  }
  const card = el("section", { class: "file-card mb-fade" });
  const head = el("button", { class: "file-head" },
    el("div", { class: "score-bar", style: `background:${heat(file.score)}` }),
    el("div", { style: "min-width:0;flex:1" },
      el("div", { class: "file-path mono" }, file.file),
      el("div", { class: "file-summary" },
         `${file.chunks.length} spans · ${file.symbols.length} symbols`
         + (file.neighbors.length ? ` · linked to ${file.neighbors.length}` : ""))),
    el("span", { class: "mono", style: "font-size:11px;color:var(--muted)" },
       file.score.toFixed(2)),
    el("div", { class: "chev" }, icon("chevron", 14)));
  head.addEventListener("click", () => {
    card.classList.toggle("open");
    body.style.display = card.classList.contains("open") ? "grid" : "none";
  });
  head.addEventListener("dblclick", () => onOpen(file.file));
  body.style.display = "none";
  card.append(head, body);
  return card;
}

function relatedCard(file: Tier2File, onOpen: (file: string) => void): HTMLElement {
  const card = el("div", { class: "t2-card mb-fade" },
    el("div", { style: "display:flex;gap:10px;align-items:center" },
      el("div", { class: "file-path mono", style: "flex:1;font-size:12px" }, file.file),
      ...(file.via_graph ? [el("span", { class: "kind-pill" }, "graph")] : []),
      el("span", { class: "mono", style: "font-size:10.5px;color:var(--muted)" },
         file.score.toFixed(2))),
    ...(file.doc ? [el("div", { class: "file-summary" }, file.doc)] : []),
    el("div", { style: "display:flex;gap:5px;flex-wrap:wrap;margin-top:8px" },
       ...file.symbols.slice(0, 4).map((symbol) =>
         el("span", { class: "file-pill mono" }, symbol.name))));
  card.addEventListener("click", () => onOpen(file.file));
  return card;
}

function heat(score: number): string {
  return score >= 1 ? "var(--accent)" : "var(--border2)";
}
