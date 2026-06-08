import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { StatusPillComponent } from './status-pill.component';
import { shortId } from '../shared/ui-utils';

@Component({
  selector: 'radar-pipeline-board',
  standalone: true,
  imports: [CommonModule, StatusPillComponent],
  template: `
    <section class="glass-card">
      <div class="panel-heading">
        <div>
          <span class="eyebrow">PIPELINES</span>
          <h2>Running processes</h2>
        </div>
      </div>
      <div class="pipeline-columns">
        <div>
          <h3>Ingestion</h3>
          <article *ngFor="let run of ingestionRuns">
            <radar-status-pill [label]="run.status"></radar-status-pill>
            <strong>{{ run.source_id || 'source run' }}</strong>
            <small>{{ shortId(run.id) }} / {{ run.total_inserted || 0 }} inserted</small>
          </article>
        </div>
        <div>
          <h3>Enrichment</h3>
          <article *ngFor="let run of enrichmentRuns">
            <radar-status-pill [label]="run.status"></radar-status-pill>
            <strong>{{ shortId(run.id) }}</strong>
            <small>{{ run.success_count || 0 }} success / {{ run.failed_count || 0 }} failed</small>
          </article>
        </div>
      </div>
    </section>
  `,
})
export class PipelineBoardComponent {
  @Input() ingestionRuns: any[] = [];
  @Input() enrichmentRuns: any[] = [];
  shortId = shortId;
}
