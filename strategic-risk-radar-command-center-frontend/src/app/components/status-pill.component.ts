import { Component, Input } from '@angular/core';
import { riskClass } from '../ui';

@Component({
  selector: 'cc-status-pill',
  standalone: true,
  template: `<span class="status-pill" [class]="riskClass(label)">{{ label || 'unknown' }}</span>`,
})
export class StatusPillComponent {
  @Input() label = '';
  riskClass = riskClass;
}
