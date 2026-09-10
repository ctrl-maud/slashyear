/** Wikipedia's list shorthand, expanded for reading: "(b. 1473)" becomes "(born 1473)"
 *  and "(d. 275)" becomes "(died 275)". A reader shouldn't need to know the convention
 *  to know which is which (issue #1). Display only — the data files and the API keep
 *  the source's own characters, and the substitution is reversible by inspection. */
export function readable(text: string): string {
  return text.replace(/\((b|d)\.\s+(?=[^)\s])/g, (_m, k: string) => (k === "b" ? "(born " : "(died "));
}
