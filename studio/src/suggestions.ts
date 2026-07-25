/* The questions a repository authored about ITSELF.
 *
 * From `megabrain.json`, and worth surfacing because the hardest part of using
 * this engine is knowing what to ask a codebase you have never read. A repo
 * that ships its own starter questions answers that for the newcomer.
 */
import { api } from "./api.js";
import { el, fill } from "./dom.js";

export function suggestionStrip(repo: () => string | undefined,
                                onPick: (question: string) => void): HTMLElement {
  const strip = el("div", { class: "stats-row", style: "gap:6px" });
  void load();
  return strip;

  async function load(): Promise<void> {
    try {
      const project = await api.project(repo());
      if (project.malformed) {
        // Never silent: somebody edited that file expecting it to matter.
        fill(strip, el("span", { class: "toast" },
          `${project.config_file} could not be parsed — defaults are in use`));
        return;
      }
      if (!project.queries.length) return;
      fill(strip, el("span", { class: "dim" }, "try:"),
        ...project.queries.slice(0, 6).map((question) => {
          const chip = el("button", { class: "chip" }, question);
          chip.addEventListener("click", () => onPick(question));
          return chip;
        }));
    } catch {
      // A repo with no config is the common case, not a failure to report.
    }
  }
}
