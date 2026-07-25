/* The questions a repository authored about ITSELF.
 *
 * From `megabrain.json`, and worth surfacing because the hardest part of using
 * this engine is knowing what to ask a codebase you have never read. A repo
 * that ships its own starter questions answers that for the newcomer.
 */
import { api } from "./api.js";
import { el, fill } from "./dom.js";

export interface Suggestions {
  root: HTMLElement;
  /* Called whenever the selected repository changes. The strip used to load
   * ONCE at construction, so it showed the first repo's questions for the rest
   * of the session — which read as "the suggestions never change". */
  reload(): void;
}

export function suggestionStrip(repo: () => string | undefined,
                                onPick: (question: string) => void): Suggestions {
  const strip = el("div", { class: "stats-row", style: "gap:6px" });
  void load();
  return { root: strip, reload: () => void load() };

  async function load(): Promise<void> {
    try {
      const project = await api.project(repo());
      if (project.malformed) {
        // Never silent: somebody edited that file expecting it to matter.
        fill(strip, el("span", { class: "toast" },
          `${project.config_file} could not be parsed — defaults are in use`));
        return;
      }
      if (!project.queries.length) {
        fill(strip);        // CLEARED, not left alone: stale chips from the
        return;            // previously selected repo are the bug itself
      }
      const label = project.queries_source === "file"
        ? "this repo asks:" : "from this repo's graph:";
      fill(strip, el("span", { class: "dim" }, label),
        ...project.queries.slice(0, 6).map((question) => {
          const chip = el("button", { class: "chip" }, question);
          chip.addEventListener("click", () => onPick(question));
          return chip;
        }));
    } catch {
      fill(strip);         // and never leave another repo's questions behind
    }
  }
}
