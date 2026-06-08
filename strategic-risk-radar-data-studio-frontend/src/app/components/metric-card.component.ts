import { Component, Input } from '@angular/core';

@Component({
  selector: 'radar-metric-card',
  standalone: true,
  template: `
    <article class="metric-card" [class.warn]="tone === 'warn'" [class.hot]="tone === 'hot'">
      <span>{{ label }}</span>
      <strong>{{ value }}</strong>
      <small>{{ hint }}</small>
    </article>
  `,
})
export class MetricCardComponent {
  @Input() label = '';
  @Input() value: string | number = 0;
  @Input() hint = '';
  @Input() tone: 'normal' | 'warn' | 'hot' = 'normal';
}
