import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { StatusPillComponent } from './status-pill.component';
import { asList, riskClass } from '../ui';

@Component({
  selector: 'cc-event-card',
  standalone: true,
  imports: [CommonModule, StatusPillComponent],
  template: `
    <button class="event-card" (click)="open.emit(event)">
      <div class="event-top">
        <cc-status-pill [label]="event.risk_level"></cc-status-pill>
        <b [class]="riskClass(event.risk_level)">{{ event.risk_score || event.highest_article_risk || 0 }}/100</b>
      </div>
      <h3>{{ event.title }}</h3>
      <p>{{ event.uae_impact || event.summary || 'Awaiting UAE impact summary.' }}</p>
      <div class="chips">
        <span *ngFor="let item of asList(event.primary_domains).slice(0, 3)">{{ item }}</span>
        <span *ngFor="let item of asList(event.affected_kpis).slice(0, 2)">{{ item }}</span>
      </div>
      <small>{{ event.article_count || 0 }} articles / {{ event.event_type || 'strategic event' }}</small>
    </button>
  `,
})
export class EventCardComponent {
  @Input() event: any;
  @Output() open = new EventEmitter<any>();
  asList = asList;
  riskClass = riskClass;
}
