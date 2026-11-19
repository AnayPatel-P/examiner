/** eCFR link for a "12 CFR 1005.x(...)" citation; null for fee-schedule entries. */
export function ecfrUrl(cite: string): string | null {
  const m = /^12 CFR (1005\.\d+)(.*)$/.exec(cite.trim())
  if (!m) return null
  const [, section, para] = m
  const base = `https://www.ecfr.gov/current/title-12/part-1005/section-${section}`
  return para ? `${base}#p-${section}${para}` : base
}
