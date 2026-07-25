/* The file panel: what a pointer expands into.
 *
 * Shows the INDEXED text, and says so when the working tree has moved on. The
 * lines a bundle pointed at were the indexed ones; quietly serving newer text
 * would answer a question about code the ranking never saw.
 */
import { api } from "./api.js";
import type { FileView } from "./contracts.js";
import { code, el, fill } from "./dom.js";

export interface FilePanel {
  open(file: string, symbol?: string): Promise<void>;
}

export function filePanel(host: HTMLElement, repo: () => string | undefined,
                          onNode: (file: string) => void): FilePanel {
  return {
    async open(file: string, symbol?: string): Promise<void> {
      fill(host, el("p", { class: "dim" }, `loading ${file}…`));
      const view = await api.file(file, repo(), symbol);
      fill(host, ...render(view, onNode));
    },
  };
}

function render(view: FileView, onNode: (file: string) => void): HTMLElement[] {
  const out: HTMLElement[] = [
    el("div", { class: "file-head" },
      el("strong", {}, view.file),
      el("span", { class: "dim" }, ` L${view.start_line}-${view.end_line}`),
      view.symbol ? el("span", { class: "tag" }, view.symbol) : el("span"),
      el("button", { class: "ghost", onclick: () => onNode(view.file) }, "dependencies")),
  ];
  if (view.stale) {
    out.push(el("p", { class: "warn" },
      "the file on disk has changed since it was indexed — this is the indexed " +
      "text. Re-index to see the current one."));
  }
  out.push(code(view.text, view.start_line));
  if (view.symbols.length) {
    out.push(el("h4", {}, "declares"),
      el("ul", { class: "outline" }, ...view.symbols.map((symbol) =>
        el("li", {}, el("span", { class: "dim" }, `${symbol.line} `),
           symbol.signature ?? symbol.name))));
  }
  return out;
}
