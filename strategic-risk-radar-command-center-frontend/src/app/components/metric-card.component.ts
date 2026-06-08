import { Component, Input } from '@angular/core';

@Component({
  selector: 'cc-metric-card',
  standalone: true,
  template: `
    <article class="metric-card">
      <small>{{ label }}</small>
      <strong>{{ value }}</strong>
      <span>{{ hint }}</span>
    </article>
  `,
})
export class MetricCardComponent {
  @Input() label = '';
  @Input() value: string | number = 0;
  @Input() hint = '';
}
