/* CODE or DOCS, never a blend — shared by search and ask.
 *
 * One component because both views ask the same question of the same engine.
 * The rule behind it: with both indexed, a long README wins on prose-shaped
 * questions and buries the implementation it describes, so the choice is
 * explicit rather than guessed from the query's wording.
 */
import { el } from "./dom.js";

export type Content = "code" | "docs" | undefined;

export interface Scope {
  root: HTMLElement;
  value(): Content;
}

/** `initial` differs by view: search lets both compete, ask defaults to CODE —
 *  a walkthrough diluted with prose explains the docs, not the mechanism. */
export function scopePicker(initial: Content = undefined): Scope {
  const options: [string, Content][] = [
    ["Both", undefined], ["Code", "code"], ["Docs", "docs"]];
  let chosen: Content = initial;
  const root = el("div", { style: "display:flex;gap:4px;margin-right:4px" });
  const buttons = options.map(([label, value]) => {
    const button = el("button", { class: "chip" }, label);
    if (value === initial) button.classList.add("on");
    button.addEventListener("click", () => {
      chosen = value;
      for (const other of buttons) other.classList.remove("on");
      button.classList.add("on");
    });
    return button;
  });
  root.append(...buttons);
  return { root, value: () => chosen };
}
