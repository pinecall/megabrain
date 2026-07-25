/* Indexing, with a progress bar that means something.
 *
 * The only operation here that takes minutes, and the only one whose progress
 * is a real count rather than a spinner — so it gets the real bar.
 */
import { api } from "../api.js";
import { el, fill, need } from "../dom.js";

export function indexOverlay(repo: string | undefined,
                             onError: (failure: unknown) => void): void {
  const host = need("overlays");
  if (!repo) return onError("select a repository first");
  const bar = el("div", { class: "progress-bar indet" });
  const label = el("div", { class: "card-sub" }, "starting…");
  const close = el("button", { class: "close-btn" }, "✕");
  close.addEventListener("click", () => fill(host));

  fill(host, el("div", { class: "overlay-bg" },
    el("div", { class: "card" },
      el("div", { class: "card-head" },
        el("div", {}, el("div", { class: "card-title" }, "Re-index"),
           el("div", { class: "card-sub mono" }, repo)),
        close),
      el("div", { style: "padding:0 24px 22px;display:grid;gap:12px" },
        el("div", { class: "progress-track" }, bar), label))));

  const running = api.index(repo, (name, data) => {
    const event = data as Record<string, unknown>;
    if (name === "progress" && event["type"] === "file") {
      const done = Number(event["i"] ?? 0);
      const total = Number(event["n"] ?? 1);
      bar.classList.remove("indet");
      bar.style.width = `${Math.round((done / total) * 100)}%`;
      label.textContent = `${done}/${total} · ${String(event["file"] ?? "")}`;
    } else if (name === "done") {
      bar.classList.remove("indet");
      bar.style.width = "100%";
      label.textContent = `${String(event["chunks"])} chunks · `
        + `${String(event["edges"])} edges · ${String(event["seconds"])}s`;
    } else if (name === "error") {
      onError(String(event["error"] ?? "indexing failed"));
      fill(host);
    }
  });
  running.done.catch(onError);
}
