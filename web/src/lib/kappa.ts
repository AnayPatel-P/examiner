/** Landis and Koch's plain-language bands for Cohen's kappa. */
export function kappaWord(k: number | null): string {
  if (k === null) return 'No data'
  if (k < 0) return 'Worse than chance'
  if (k <= 0.2) return 'Slight'
  if (k <= 0.4) return 'Fair'
  if (k <= 0.6) return 'Moderate'
  if (k <= 0.8) return 'Substantial'
  return 'Almost perfect'
}
