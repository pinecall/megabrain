/* The code navigator: one file, slid over everything else.
 *
 * A panel rather than a page because it is opened FROM a result and closed
 * back into it — navigating away and back would lose the search that led here.
 */
import { api } from "../api.js";
import type { FileView } from "../contracts.js";
import { el, fill, need } from "../dom.js";

export async function openFile(file: string, repo: string | undefined,
                               onError: (failure: unknown) => void): Promise<void> {
  const host = need("viewer");
  fill(host, el("div", { class: "viewer-panel" },
    el("div", { class: "empty" }, el("div", { class: "spinner" }), file)));
  try {
    fill(host, panel(await api.file(file, repo), () => fill(host)));
  } catch (failure) {
    fill(host);
    onError(failure);
  }
}

function panel(view: FileView, close: () => void): HTMLElement {
  const closer = el("button", { class: "close-btn" }, "✕");
  closer.addEventListener("click", close);
  return el("div", { class: "viewer-panel" },
    el("div", { class: "card-head" },
      el("div", { style: "min-width:0" },
        el("div", { class: "card-title mono" }, view.file),
        el("div", { class: "card-sub" },
           `L${view.start_line}-${view.end_line}`
           + (view.symbol ? ` · ${view.symbol}` : ""))),
      closer),
    ...(view.stale
      ? [el("div", { class: "toast", style: "margin:0 24px 12px" },
           "the file on disk has changed since it was indexed — this is the "
           + "INDEXED text")]
      : []),
    el("div", { style: "display:flex;flex:1;min-height:0" },
      el("div", { class: "mono", style: "flex:1;overflow:auto;padding:8px 0" },
         ...lines(view)),
      el("div", { class: "viewer-syms" },
         ...view.symbols.map((symbol) =>
           el("div", { class: "flag-row mono" },
              el("span", { class: "flag-reason" }, symbol.kind),
              el("span", {}, symbol.name))))));
}

function lines(view: FileView): HTMLElement[] {
  return view.text.split("\n").map((line, offset) =>
    el("div", { class: "vln" },
      el("span", { class: "vno mono" }, String(view.start_line + offset)),
      el("span", { class: "vcode" }, line)));
}
