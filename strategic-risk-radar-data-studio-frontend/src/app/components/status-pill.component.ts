import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { riskClass } from '../shared/ui-utils';

@Component({
  selector: 'radar-status-pill',
  standalone: true,
  imports: [CommonModule],
  template: `<span class="status-pill" [ngClass]="cssClass">{{ label }}</span>`,
})
export class StatusPillComponent {
  @Input() label = 'unknown';
  @Input() mode: 'status' | 'risk' = 'status';

  get cssClass(): string {
    if (this.mode === 'risk') return riskClass(this.label);
    const value = (this.label || '').toLowerCase();
    if (value.includes('running')) return 'status-running';
    if (value.includes('failed') || value.includes('error')) return 'status-failed';
    if (value.includes('review') || value.includes('warning')) return 'status-warning';
    if (value.includes('completed') || value.includes('ok') || value.includes('enriched')) return 'status-ok';
    return 'status-muted';
  }
}
