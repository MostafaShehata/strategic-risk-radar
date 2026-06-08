export function asList(value: unknown): string[] {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(String) : [value];
    } catch {
      return [value];
    }
  }
  return [String(value)];
}

export function riskClass(level: string | undefined): string {
  return `risk-${String(level || 'low').toLowerCase()}`;
}

export function shortId(id: string | undefined): string {
  return id ? id.slice(0, 8) : '';
}
