/* Indexing, reported as an installer reports: named steps, one bar, real counts.
 *
 * The version this replaces was a single indeterminate bar shuttling back and
 * forth with no text. It was unreadable in the two ways that matter: it never
 * said which phase was running, and it RESET — indexing filled it to 100%, then
 * the card pass started over from 0 on the same bar, which reads as a hang or a
 * restart rather than as progress.
 *
 * So: one row per phase, each with its own state and its own numbers, and the
 * bar belongs to the row that is running. A phase that did nothing says so with
 * a reason. Nothing here animates without a number behind it.
 */
import { el, fill } from "../dom.js";

export type PhaseName = "scan" | "embed" | "write" | "cards";

interface Phase {
  name: PhaseName;
  title: string;
  row: HTMLElement;
  detail: HTMLElement;
  bar: HTMLElement;
  state: "waiting" | "running" | "done" | "skipped";
}

export interface Progress {
  root: HTMLElement;
  /* One engine event. Returns nothing: the DOM is the state. */
  event(data: Record<string, unknown>): void;
  finish(report: Record<string, unknown>): void;
  fail(message: string): void;
}

const TITLES: Record<PhaseName, string> = {
  scan: "Reading files",
  embed: "Embedding what changed",
  write: "Writing the index",
  cards: "Writing the mental map",
};

export function indexProgress(withCards: boolean): Progress {
  const names: PhaseName[] = withCards ? ["scan", "embed", "write", "cards"]
    : ["scan", "embed", "write"];
  const phases = names.map(phase);
  const summary = el("div", { class: "install-summary" });
  const root = el("div", { class: "install" }, ...phases.map((one) => one.row), summary);
  const find = (name: PhaseName): Phase | undefined =>
    phases.find((one) => one.name === name);

  /* Reaching a phase implies the ones before it are done: the engine reports
   * what it is doing, never what it has stopped doing, and inferring that here
   * beats asking every phase to announce its own end. */
  const enter = (name: PhaseName): Phase | undefined => {
    const target = find(name);
    if (!target) return undefined;
    for (const one of phases) {
      if (one === target) break;
      if (one.state === "running" || one.state === "waiting") settle(one, "done");
    }
    if (target.state !== "running") {
      target.state = "running";
      target.row.className = "install-row running";
    }
    return target;
  };

  return {
    root,
    event(data) {
      const kind = String(data["type"] ?? "");
      if (kind === "file") tick(enter("scan"), data, "file");
      else if (kind === "embed") ticked(enter("embed"), Number(data["done"] ?? 0),
                                       Number(data["total"] ?? 0), "vector");
      else if (kind === "card") tick(enter("cards"), data, "card");
    },
    finish(report) {
      for (const one of phases) settle(one, "done");
      fill(summary, ...report_lines(report, withCards));
      close(phases, report, withCards);
    },
    fail(message) {
      const running = phases.find((one) => one.state === "running") ?? phases[0];
      if (running) {
        running.row.className = "install-row failed";
        fill(running.detail, message);
      }
      fill(summary, el("div", { class: "warn-bar" }, message));
    },
  };
}

function phase(name: PhaseName): Phase {
  const detail = el("div", { class: "install-detail mono" }, "waiting");
  const bar = el("div", { class: "progress-bar" });
  const row = el("div", { class: "install-row waiting" },
    el("div", { class: "install-mark" }),
    el("div", { class: "install-body" },
      el("div", { class: "install-title" }, TITLES[name]),
      detail,
      el("div", { class: "progress-track" }, bar)));
  return { name, title: TITLES[name], row, detail, bar, state: "waiting" };
}

function tick(target: Phase | undefined, data: Record<string, unknown>,
              noun: string): void {
  if (!target) return;
  const done = Number(data["i"] ?? 0);
  const total = Number(data["n"] ?? 0);
  ticked(target, done, total, noun, String(data["file"] ?? ""));
}

function ticked(target: Phase | undefined, done: number, total: number,
                noun: string, what = ""): void {
  if (!target) return;
  target.bar.style.width = total ? `${Math.round((done / total) * 100)}%` : "0%";
  fill(target.detail, `${done}/${total} ${noun}${done === 1 ? "" : "s"}`
       + (what ? ` · ${what}` : ""));
}

function settle(target: Phase, state: "done" | "skipped"): void {
  target.state = state;
  target.row.className = `install-row ${state}`;
  target.bar.style.width = state === "done" ? "100%" : "0%";
}

/* The counts each phase ENDED with, once the report is in. A phase whose bar
 * filled but whose real answer was "nothing to do" has to say the second thing:
 * this is exactly where "0 chunks · 0 edges" used to read as a failure. */
function close(phases: Phase[], report: Record<string, unknown>,
               withCards: boolean): void {
  const changed = Number(report["changed"] ?? 0);
  const cards = report["study"] as Record<string, unknown> | undefined;
  const written = Number(cards?.["written"] ?? 0);
  const detail: Record<PhaseName, string> = {
    scan: `${report["files"]} files · ${changed} changed`
      + (Number(report["skipped"] ?? 0) ? ` · ${report["skipped"]} skipped` : ""),
    embed: changed ? `${changed} files embedded` : "nothing changed — nothing to embed",
    write: changed ? `${report["chunks"]} chunks · ${report["edges"]} edges`
      : `no writes — the index already holds ${report["total_chunks"]} chunks`,
    cards: cardDetail(report, cards),
  };
  for (const one of phases) {
    fill(one.detail, detail[one.name]);
    const nothing = one.name === "embed" || one.name === "write" ? !changed
      : one.name === "cards" ? withCards && !written : false;
    if (nothing) settle(one, "skipped");
  }
}

function cardDetail(report: Record<string, unknown>,
                    cards: Record<string, unknown> | undefined): string {
  const failure = report["study_error"];
  if (typeof failure === "string") return `not written: ${failure}`;
  if (!cards) return "not requested";
  const written = Number(cards["written"] ?? 0);
  const held = written + Number(cards["unchanged"] ?? 0);
  const degraded = Number(cards["degraded"] ?? 0);
  const skipped = Number(cards["skipped"] ?? 0);
  if (!held && skipped) {
    // The case that read as a silent failure: every file was skipped because it
    // declares nothing, so there was never a card to write. Saying "0 written"
    // and stopping there is what made it look broken.
    return `nothing to describe — ${skipped} files declare no symbols`;
  }
  return (written ? `${written} written · ` : "already complete · ")
    + `${held} cards in the map`
    + (degraded ? ` · ${degraded} degraded to the raw skeleton` : "")
    + (skipped ? ` · ${skipped} skipped (no symbols)` : "");
}

/* One sentence, and it must be true of BOTH outcomes: a repository that was
 * fully re-indexed and one that had nothing to do. */
function report_lines(report: Record<string, unknown>,
                      withCards: boolean): HTMLElement[] {
  const changed = Number(report["changed"] ?? 0);
  const headline = changed
    ? `Indexed ${changed} changed file${changed === 1 ? "" : "s"} in ${report["seconds"]}s`
    : `Already up to date — nothing changed (${report["seconds"]}s)`;
  const lines = [el("div", { class: "install-head" }, headline),
                 el("div", { class: "install-totals mono" },
                    `the index now holds ${report["total_files"]} files · `
                    + `${report["total_chunks"]} chunks · `
                    + `${report["total_symbols"]} symbols · `
                    + `${report["total_edges"]} edges`)];
  const stale = Number(report["stale_flows"] ?? 0);
  if (stale) {
    lines.push(el("div", { class: "install-note mono" },
      `${stale} cached walkthrough${stale === 1 ? "" : "s"} dropped — their `
      + "sources changed"));
  }
  const failure = report["study_error"];
  if (withCards && typeof failure === "string") {
    lines.push(el("div", { class: "warn-bar" }, `no mental map: ${failure}`));
  }
  return lines;
}
