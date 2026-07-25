/* Adding a repository: type a path, SEE what it would read, then index it.
 *
 * The census first, always. Pointing this engine at a large directory costs
 * real money and minutes, and the census costs neither — so the destructive,
 * expensive step is never the first click. It also shows what would be
 * SKIPPED, by name: a file missing from an index is invisible afterwards, and
 * the moment to notice is before.
 */
import { api } from "../api.js";
import type { ScanReport } from "../contracts.js";
import { el, fill, need } from "../dom.js";
import { indexProgress } from "./progress.js";

/* One door for both jobs. A path that is ALREADY indexed is not a different
 * feature — the census says so and the button says "Re-index", which is also
 * how somebody re-indexes the repo they have selected without hunting for a
 * second control that does almost the same thing. */
export function addRepoOverlay(current: string | undefined, onIndexed: () => void,
                               onError: (failure: unknown) => void): void {
  const host = need("overlays");
  const input = el("input", { class: "field mono", type: "text", spellcheck: "false",
                              placeholder: "~/code/my-project" }) as HTMLInputElement;
  input.value = current ?? "";
  const census = el("div", { style: "display:grid;gap:10px" });
  const start = el("button", { class: "btn-primary" }, "Index it");
  const preview = el("button", { class: "chip" }, "Scan");
  start.setAttribute("disabled", "true");

  const close = (): void => fill(host);
  const closer = el("button", { class: "close-btn" }, "✕");
  closer.addEventListener("click", close);

  async function look(): Promise<void> {
    if (!input.value.trim()) return;
    fill(census, el("div", { class: "empty" }, el("div", { class: "spinner" }),
                    "scanning…"));
    try {
      const report = await api.scan(input.value.trim());
      fill(census, ...render(report));
      start.textContent = report.indexed ? "Re-index" : "Index it";
      // Nothing readable is not a repository to index, and offering the button
      // anyway is how somebody ends up staring at "0 chunks · 0 edges" trying
      // to work out what broke. The census already said why, right above.
      if (report.would_index > 0) start.removeAttribute("disabled");
      else start.setAttribute("disabled", "true");
    } catch (failure) {
      start.setAttribute("disabled", "true");
      fill(census, el("div", { class: "toast" }, String(failure)));
    }
  }

  function index(): void {
    const steps = indexProgress();
    fill(census, steps.root);
    start.setAttribute("disabled", "true");
    const running = api.index(input.value.trim(), (name, data) => {
      const event = data as Record<string, unknown>;
      if (name === "progress") steps.event(event);
      else if (name === "done") { steps.finish(event); onIndexed(); }
      else if (name === "error") {
        // Shown in place AND toasted: the overlay is where the reader is
        // looking, and a toast alone disappears while they read the phases.
        const message = String(event["error"] ?? "indexing failed");
        steps.fail(message);
        onError(message);
      }
    });
    running.done.catch((failure: unknown) => {
      steps.fail(String(failure));
      onError(failure);
    });
  }

  preview.addEventListener("click", () => void look());
  start.addEventListener("click", index);
  input.addEventListener("keydown", (event) => {
    if ((event as KeyboardEvent).key === "Enter") void look();
  });

  fill(host, el("div", { class: "overlay-bg" },
    el("div", { class: "card" },
      el("div", { class: "card-head" },
        el("div", {}, el("div", { class: "card-title" }, "Add a repository"),
           el("div", { class: "card-sub" },
              "the census is free — index only once you like what it says")),
        closer),
      el("div", { style: "padding:0 24px 22px;display:grid;gap:14px;overflow:auto" },
        el("div", { style: "display:flex;gap:8px" }, input, preview),
        census,
        el("div", { style: "display:flex;justify-content:flex-end" }, start)))));
  input.focus();
  if (input.value) void look();     // the selected repo, already censused
}

function unreadable(report: ScanReport): HTMLElement[] {
  const found = Object.entries(report.unsupported);
  if (!found.length) return [];
  const listed = found.slice(0, 6)
    .map(([extension, count]) => `${count} ${extension}`).join(" · ");
  const nothing = report.would_index === 0;
  return [el("div", { class: nothing ? "warn-bar" : "info-bar" },
    nothing ? el("b", {}, "nothing here can be indexed yet") : el("span", {}, "also found"),
    ` ${listed}`,
    el("div", { class: "mono small" },
       `this build reads ${report.supported.join(", ")}`))];
}

function render(report: ScanReport): HTMLElement[] {
  const reasons = new Map<string, number>();
  for (const entry of report.skipped) {
    reasons.set(entry.reason, (reasons.get(entry.reason) ?? 0) + 1);
  }
  return [
    el("div", { class: "info-bar" },
      el("b", {}, String(report.would_index)), "files would be indexed",
      ...(report.indexed
        ? [el("span", { class: "index-tag chg" }, "already indexed")] : [])),
    ...unreadable(report),
    el("div", { style: "display:flex;gap:5px;flex-wrap:wrap" },
      ...Object.entries(report.by_extension).slice(0, 10).map(([ext, count]) =>
        el("span", { class: "file-pill mono" }, `${ext} ${count}`))),
    ...(reasons.size
      ? [el("div", { class: "stats-row" }, "skipped:",
           ...[...reasons].map(([reason, count]) =>
             el("span", { class: "kind-pill" }, `${reason} ${count}`)))]
      : []),
    // The named ones only: "excluded" is a rule working, the others are a
    // file the reader may want back.
    ...report.skipped.filter((entry) => entry.reason !== "excluded").slice(0, 8)
      .map((entry) => el("div", { class: "flag-row mono" },
        el("span", { class: "flag-reason" }, entry.reason), entry.file)),
  ];
}
