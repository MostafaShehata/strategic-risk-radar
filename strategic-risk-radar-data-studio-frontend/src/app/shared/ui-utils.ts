export function riskClass(level: string | null | undefined): string {
  const value = (level || '').toLowerCase();
  if (value === 'critical') return 'risk-critical';
  if (value === 'high') return 'risk-high';
  if (value === 'medium') return 'risk-medium';
  if (value === 'low') return 'risk-low';
  return 'risk-unknown';
}

export function shortId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : 'n/a';
}

export function numberValue(value: unknown): number {
  return Number(value || 0);
}
