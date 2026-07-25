/* Walking a route: every call → definition pair, one step at a time.
 *
 * This is what makes a path more than a diagram. Each step is a real place in
 * real code — the call, then the definition it lands in — and the canvas rings
 * the node the step is talking about while the pulse travels that hop. A reader
 * follows a connection through the codebase without opening a single file
 * themselves, and every frame of it came from the index.
 */
import type { CodeSnip, GraphPath } from "../contracts.js";

export interface Step {
  file: string;
  hop: number;
  kind: "the call" | "the definition";
  line: number;
  highlighted: number[];
  symbol: string;
  inSymbol?: string | null | undefined;
  snip: CodeSnip;
}

export interface Walk {
  steps: Step[];
  at: number;
  elapsed: number;
  auto: boolean;
}

/* Auto-advance after this long on one step, and the pulse's own loop length. */
export const STEP_SECONDS = 6;
export const PULSE_SECONDS = 3.4;

export function walkSteps(path: GraphPath | null): Step[] {
  if (!path?.found) return [];
  const steps: Step[] = [];
  path.hops.slice(1).forEach((hop, index) => {
    const code = hop.code;
    if (!code) return;
    if (code.use) steps.push(step(code.use, index + 1, "the call", code.symbol));
    if (code.definition) {
      steps.push(step(code.definition, index + 1, "the definition", code.symbol));
    }
  });
  return steps;
}

function step(snip: CodeSnip, hop: number, kind: Step["kind"], symbol: string): Step {
  const rows = snip.hi_rows ?? [];
  return {
    file: snip.file, hop, kind, symbol, inSymbol: snip.in_symbol,
    // The absolute line, from the window's start plus the marked row: the
    // studio opens the editor HERE, and off by a window is off by a screen.
    line: snip.start_line + (rows[0] ?? 0),
    highlighted: rows.map((row) => snip.start_line + row),
    snip,
  };
}

export function advance(walk: Walk, seconds: number): boolean {
  walk.elapsed += seconds;
  if (walk.auto && walk.elapsed > STEP_SECONDS) {
    if (walk.at < walk.steps.length - 1) {
      walk.at += 1;
      walk.elapsed = 0;
      return true;                     // the card has to repaint
    }
    walk.auto = false;                 // the end: stop, do not loop the route
    walk.elapsed = 0;
    return true;
  }
  if (walk.elapsed > PULSE_SECONDS) walk.elapsed = 0;   // the pulse loops
  return false;
}
