/* The judge toggle — shared by search and brief, off by default.
 *
 * One component because both views offer the same lane of the same engine, and
 * the same caveat: it costs a model call (a second or two) and it can only
 * REORDER — the deterministic answer stands whenever the judge cannot speak.
 * The default is off for the same reason it is off in the engine: an answer in
 * milliseconds that never depends on a model being up is the product's shape.
 */
import { el } from "./dom.js";

export interface JudgeToggle {
  root: HTMLElement;
  on(): boolean;
}

export function judgeToggle(): JudgeToggle {
  let active = false;
  const button = el("button", {
    class: "chip",
    title: "one model call reorders RELATED by the task's edit surface — "
      + "slower, never drops a file",
  }, "⚖ judge");
  button.addEventListener("click", () => {
    active = !active;
    button.classList.toggle("on", active);
  });
  return { root: button, on: () => active };
}
