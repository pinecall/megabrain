/* The ask view: the retrieval trace, then the walkthrough as it is written.
 *
 * The retrieval bar appears BEFORE the model has said anything, and that
 * ordering is the point: the deterministic answer is already complete, and the
 * model is only explaining it. Somebody who reads the file list and stops has
 * lost nothing.
 */
import { api } from "../api.js";
import { el, fill } from "../dom.js";
import { icon } from "../icons.js";
import { renderMarkdown } from "../markdown.js";

export interface AskView {
  root: HTMLElement;
  focus(): void;
}

export function askView(repo: () => string | undefined,
                        onError: (failure: unknown) => void): AskView {
  const input = el("input", {
    class: "query-input", type: "search", autocomplete: "off", spellcheck: "false",
    placeholder: "how does retry and backoff work end to end?",
  }) as HTMLInputElement;
  const trace = el("div", {});
  const answer = el("div", { class: "synth", style: "display:none;margin-top:22px" });
  let running: { done: Promise<void>; abort: () => void } | null = null;

  const run = async (): Promise<void> => {
    if (!input.value.trim() || running) return;
    fill(trace, el("div", { class: "info-bar" },
      el("div", { class: "spinner" }), "retrieving…"));
    fill(answer);
    answer.style.display = "none";
    const markdown: string[] = [];
    try {
      running = api.ask(input.value.trim(), repo(), (name, data) =>
        onEvent(name, data, trace, answer, markdown));
      await running.done;
    } catch (failure) {
      onError(failure);
    } finally {
      running = null;
      answer.querySelector(".caret")?.remove();
    }
  };
  input.addEventListener("keydown", (event) => {
    if ((event as KeyboardEvent).key === "Enter") void run();
  });
  const go = el("button", { class: "badge" }, icon("spark", 13), "ASK");
  go.addEventListener("click", () => void run());

  return {
    root: el("div", { class: "view-wrap" },
      el("div", { class: "query-wrap" },
        el("div", { class: "query-icon" }, icon("brain")), input, go),
      trace, answer),
    focus: () => input.focus(),
  };
}

function onEvent(name: string, data: unknown, trace: HTMLElement,
                 answer: HTMLElement, markdown: string[]): void {
  const event = data as Record<string, unknown>;
  if (name === "retrieval") {
    fill(trace, retrievalBar(event));
  } else if (name === "narrating") {
    trace.append(el("div", { class: "foot-bar" },
      el("div", { class: "chip-ic" }, icon("spark", 11)),
      `narrating over ${String(event["candidates"])} chunks`));
    answer.style.display = "block";
  } else if (name === "delta") {
    markdown.push(String(event["text"] ?? ""));
    fill(answer, ...renderMarkdown(markdown.join("")),
         el("span", { class: "caret" }));
  } else if (name === "narrated") {
    fill(answer, ...renderMarkdown(markdown.join("")));
    trace.append(el("div", { class: "foot-bar" },
      el("b", {}, `${String(event["ms"])}ms`), "walkthrough complete"));
  } else if (name === "error") {
    trace.append(el("div", { class: "toast" }, String(event["error"] ?? "failed")));
  }
}

function retrievalBar(event: Record<string, unknown>): HTMLElement {
  const core = (event["core"] as string[] | undefined) ?? [];
  return el("div", { class: "info-bar" },
    el("div", { class: "chip-ic" }, icon("search", 11)),
    el("b", {}, `${String(event["ms"])}ms`),
    "retrieved", el("div", { class: "sdot" }),
    `${core.length} core · ${String(event["related"])} related`,
    el("div", { style: "display:flex;gap:6px;flex-wrap:wrap;width:100%" },
       ...core.map((file) => el("span", { class: "file-pill mono" }, file))));
}
