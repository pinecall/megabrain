/* The brief view: the mental model for a question — prose, relations, no code.
 *
 * Every file is one card: what it IS (written at study time by a model, gated
 * against its own declarations), who it uses and who uses it (read live from
 * the graph, so it cannot be stale), and its interface. Bodies are deliberately
 * absent — this tab exists to be readable in one screen, and the code is one
 * click away in Search or the file viewer.
 */
import { ApiFailure, api } from "../api.js";
import type { Brief, BriefFile } from "../contracts.js";
import { el, fill } from "../dom.js";
import { icon } from "../icons.js";
import { judgeToggle } from "../judge.js";
import { suggestionStrip } from "../suggestions.js";

export interface BriefView {
  /* Re-read anything per-repo — called when the selection changes. */
  refresh(): void;
  root: HTMLElement;
  focus(): void;
}

const RELATIONS_SHOWN = 8;

export function briefView(repo: () => string | undefined,
                          onOpen: (file: string) => void,
                          onError: (failure: unknown) => void): BriefView {
  const input = el("input", {
    class: "query-input", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder: "how does indexing turn a file into chunks and edges?",
  }) as HTMLInputElement;
  const results = el("div", {});
  const stats = el("div", { class: "stats-row" });
  const judge = judgeToggle();

  const run = async (): Promise<void> => {
    if (!input.value.trim()) return;
    fill(results, el("div", { class: "empty" }, el("div", { class: "spinner" }),
                     "reading the map…"));
    fill(stats);
    try {
      render(await api.brief(input.value.trim(), repo(), undefined,
                             judge.on() || undefined),
             results, stats, onOpen);
    } catch (failure) {
      /* A repo nobody studied is the expected first visit, not a fault: it
       * gets the one command that fixes it, in the panel, instead of a toast
       * that scrolls away in eight seconds. */
      if (failure instanceof ApiFailure && failure.code === "study_not_found") {
        fill(results, notStudied());
      } else {
        fill(results);
        onError(failure);
      }
    }
  };
  input.addEventListener("keydown", (event) => {
    if ((event as KeyboardEvent).key === "Enter") void run();
  });
  const go = el("button", { class: "badge" }, icon("brain", 13), "BRIEF");
  go.addEventListener("click", () => void run());

  const suggestions = suggestionStrip(repo, (question) => {
    input.value = question; void run();
  });

  return {
    root: el("div", { class: "view-wrap" },
      el("div", { class: "query-wrap" },
        el("div", { class: "query-icon" }, icon("brain")), input, judge.root, go),
      suggestions.root, stats, results),
    focus: () => input.focus(),
    refresh: () => suggestions.reload(),
  };
}

function render(brief: Brief, results: HTMLElement, stats: HTMLElement,
                onOpen: (file: string) => void): void {
  fill(stats, el("b", {}, String(brief.files.length)), ` of ${brief.considered} files`,
       el("div", { class: "sdot" }), el("b", {}, `${brief.ms}ms`),
       el("div", { class: "sdot" }),
       /* Stated on screen because it is the whole claim of this tab: the prose
        * was written once, at study time, and reading it costs nothing. */
       "0 model calls", el("div", { class: "sdot" }), brief.repo);
  fill(results, ...brief.files.map((file) => card(file, onOpen)));
}

function card(file: BriefFile, onOpen: (file: string) => void): HTMLElement {
  const path = el("button", { class: "file-path mono brief-path" }, file.file);
  path.addEventListener("click", () => onOpen(file.file));
  return el("section", { class: "file-card brief-card mb-fade" },
    el("div", { class: "brief-head" },
      path,
      ...(file.degraded
        ? [el("span", { class: "kind-pill", "data-tip":
             "no card for this file — showing its declarations instead" },
             "skeleton")]
        : []),
      el("span", { class: "mono brief-score" }, file.score.toFixed(2))),
    el("p", { class: "brief-prose" }, file.card),
    ...relations(file),
    ...(file.symbols.length ? [iface(file)] : []));
}

function relations(file: BriefFile): HTMLElement[] {
  const rows: HTMLElement[] = [];
  if (file.imports.length) rows.push(row("→", "uses", file.imports));
  if (file.imported_by.length) rows.push(row("←", "used by", file.imported_by));
  return rows;
}

function row(arrow: string, label: string, files: string[]): HTMLElement {
  const extra = files.length - RELATIONS_SHOWN;
  return el("div", { class: "brief-rel" },
    el("span", { class: "brief-arrow mono" }, arrow),
    el("span", { class: "brief-rel-label" }, label),
    el("div", { class: "brief-pills" },
      ...files.slice(0, RELATIONS_SHOWN).map((name) =>
        el("span", { class: "file-pill mono" }, name)),
      ...(extra > 0
        ? [el("span", { class: "brief-rel-more" }, `+${extra} more`)] : [])));
}

function iface(file: BriefFile): HTMLElement {
  return el("div", { class: "brief-iface" },
    ...file.symbols.map((symbol) =>
      el("div", { class: "mono brief-sig" }, symbol.signature || symbol.name)));
}

function notStudied(): HTMLElement {
  return el("div", { class: "empty" },
    el("div", {}, "This repository has no mental map yet."),
    el("div", { class: "brief-prose", style: "max-width:46ch;text-align:center" },
       "A model reads each file's declarations once and writes what it is. "
       + "Answers after that are instant and cost nothing."),
    el("div", { class: "mono", style: "font-size:11.5px" }, "megabrain study"));
}
