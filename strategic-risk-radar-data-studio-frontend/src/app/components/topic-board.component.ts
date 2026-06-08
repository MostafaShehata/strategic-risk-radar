import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { StatusPillComponent } from './status-pill.component';

@Component({
  selector: 'radar-topic-board',
  standalone: true,
  imports: [CommonModule, StatusPillComponent],
  template: `
    <section class="glass-card">
      <div class="panel-heading">
        <div>
          <span class="eyebrow">STRATEGIC TOPICS</span>
          <h2>Topic risk board</h2>
        </div>
      </div>
      <div class="topic-list">
        <button *ngFor="let topic of topics" (click)="openTopic.emit(topic)">
          <div>
            <strong>{{ topic.title || 'Untitled model topic' }}</strong>
            <small>{{ topic.event_type || topic.topic_key }} / {{ topic.article_count || 0 }} articles</small>
          </div>
          <radar-status-pill mode="risk" [label]="topic.risk_level"></radar-status-pill>
          <b>{{ topic.highest_article_risk || topic.risk_score || 0 }}</b>
        </button>
      </div>
    </section>
  `,
})
export class TopicBoardComponent {
  @Input() topics: any[] = [];
  @Output() openTopic = new EventEmitter<any>();
}
