import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { StatusPillComponent } from './status-pill.component';

@Component({
  selector: 'radar-source-health',
  standalone: true,
  imports: [CommonModule, StatusPillComponent],
  template: `
    <section class="glass-card">
      <div class="panel-heading">
        <div>
          <span class="eyebrow">INGESTION</span>
          <h2>Source health</h2>
        </div>
      </div>
      <div class="source-list">
        <article *ngFor="let source of sources">
          <div>
            <strong>{{ source.source_id }}</strong>
            <small>{{ source.source_type }} / {{ source.last_started_at | date:'short' }}</small>
          </div>
          <radar-status-pill [label]="source.last_status"></radar-status-pill>
          <span>{{ source.last_retrieved || 0 }} retrieved</span>
          <span>{{ source.last_inserted || 0 }} new</span>
        </article>
      </div>
    </section>
  `,
})
export class SourceHealthComponent {
  @Input() sources: any[] = [];
}
