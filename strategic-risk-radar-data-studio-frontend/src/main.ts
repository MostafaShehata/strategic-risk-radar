import 'zone.js';
import { CommonModule } from '@angular/common';
import { HttpClient, provideHttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { bootstrapApplication } from '@angular/platform-browser';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <header>
      <div><span class="eyebrow">DECISION INTELLIGENCE</span><h1>Strategic Risk Radar</h1>
        <p>News ingestion operations and evidence browser</p></div>
      <button (click)="loadAll()">Refresh data</button>
    </header>

    <main>
      <section class="cards" *ngIf="overview">
        <article><label>Ingestion runs</label><strong>{{overview.total_runs}}</strong></article>
        <article><label>Stored documents</label><strong>{{overview.total_documents}}</strong></article>
        <article><label>New documents</label><strong>{{overview.total_inserted}}</strong></article>
        <article class="warning"><label>Runs with source errors</label><strong>{{overview.runs_with_errors}}</strong></article>
      </section>

      <nav>
        <button *ngFor="let item of tabs" [class.active]="tab===item" (click)="tab=item">{{item}}</button>
      </nav>

      <section *ngIf="tab==='Run Intelligence'" class="run-layout">
        <aside class="panel run-list">
          <div class="section-heading"><div><span class="eyebrow dark">RUN HISTORY</span><h2>Ingestion runs</h2></div></div>
          <button class="run-card" *ngFor="let run of runs" [class.selected]="selectedRunId===run.id" (click)="selectRun(run.id)">
            <div><strong>{{run.started_at | date:'medium'}}</strong><span class="badge" [class.bad]="run.error_count">{{run.status}}</span></div>
            <div class="mini-metrics"><span>{{run.total_retrieved}} retrieved</span><span>{{run.total_inserted}} new</span><span>{{run.error_count}} errors</span></div>
          </button>
        </aside>

        <section class="panel run-detail" *ngIf="runDetail?.run; else selectPrompt">
          <div class="section-heading">
            <div><span class="eyebrow dark">SELECTED RUN</span><h2>{{runDetail.run.started_at | date:'medium'}}</h2></div>
            <span class="badge large" [class.bad]="runDetail.run.error_count">{{runDetail.run.status}}</span>
          </div>
          <div class="summary-strip">
            <span><label>Retrieved</label><strong>{{runDetail.run.total_retrieved}}</strong></span>
            <span><label>Matched</label><strong>{{runDetail.run.total_matched}}</strong></span>
            <span><label>Inserted</label><strong>{{runDetail.run.total_inserted}}</strong></span>
            <span><label>Duplicates</label><strong>{{runDetail.run.total_duplicates}}</strong></span>
          </div>
          <article class="source-card" *ngFor="let source of runDetail.sources">
            <div class="source-title">
              <div><h3>{{source.source_id}}</h3><small>{{source.window_start | date:'medium'}} to {{source.window_end | date:'medium'}}</small></div>
              <span class="badge" [class.bad]="source.status==='error'">{{source.status}}</span>
            </div>
            <div class="source-stats">
              <span><b>{{source.request_count}}</b> requests</span><span><b>{{source.retrieved_count}}</b> retrieved</span>
              <span><b>{{source.matched_count}}</b> matched</span><span><b>{{source.inserted_count}}</b> inserted</span>
              <span><b>{{source.duplicate_count}}</b> duplicates</span><span><b>{{source.duration_ms}} ms</b> duration</span>
            </div>
            <p class="error" *ngIf="source.error_message">{{source.error_message}}</p>
            <table class="keyword-table"><thead><tr><th>Keyword</th><th>Requests</th><th>Retrieved</th><th>Matched</th><th>Inserted</th><th>Duplicates</th></tr></thead>
              <tbody><tr *ngFor="let keyword of source.keywords"><td><strong>{{keyword.keyword}}</strong></td><td>{{keyword.request_count}}</td><td>{{keyword.retrieved_count}}</td><td>{{keyword.matched_count}}</td><td>{{keyword.inserted_count}}</td><td>{{keyword.duplicate_count}}</td></tr></tbody>
            </table>
          </article>
        </section>
        <ng-template #selectPrompt><section class="panel empty">Select a run to view its sources and keywords.</section></ng-template>
      </section>

      <section class="panel" *ngIf="tab==='Documents'">
        <div class="section-heading"><div><span class="eyebrow dark">RAW EVIDENCE</span><h2>Browse ingested documents</h2></div></div>
        <div class="filters">
          <input [(ngModel)]="search" (keyup.enter)="loadDocuments()" placeholder="Search titles and summaries">
          <select [(ngModel)]="source"><option value="">All sources</option><option *ngFor="let s of sourceNames">{{s}}</option></select>
          <button (click)="loadDocuments()">Search</button>
        </div>
        <div class="documents">
          <article *ngFor="let d of documents">
            <div><span class="source">{{d.source_id}}</span><span class="keywords">{{d.keywords}}</span></div>
            <h3><a [href]="d.url" target="_blank" rel="noopener">{{d.title}}</a></h3>
            <p>{{d.summary | slice:0:300}}</p>
            <small>{{d.published_at || d.first_seen_at | date:'medium'}}</small>
          </article>
        </div>
      </section>
    </main>`,
})
class App implements OnInit {
  tabs = ['Run Intelligence', 'Documents']; tab = 'Run Intelligence';
  overview: any; runs: any[] = []; documents: any[] = []; runDetail: any;
  selectedRunId = ''; search = ''; source = ''; sourceNames: string[] = [];
  constructor(private http: HttpClient) {}
  ngOnInit() { this.loadAll(); }
  loadAll() {
    this.http.get('/api/overview').subscribe(v => this.overview = v);
    this.http.get<any[]>('/api/runs').subscribe(v => {
      this.runs = v;
      if (v.length && !this.selectedRunId) this.selectRun(v[0].id);
    });
    this.http.get<any[]>('/api/sources').subscribe(v => this.sourceNames = [...new Set(v.map(x => x.source_id))]);
    this.loadDocuments();
  }
  selectRun(id: string) {
    this.selectedRunId = id;
    this.http.get('/api/runs/' + id).subscribe(v => this.runDetail = v);
  }
  loadDocuments() {
    const q = new URLSearchParams({search: this.search, source: this.source});
    this.http.get<any[]>('/api/documents?' + q).subscribe(v => this.documents = v);
  }
}

bootstrapApplication(App, {providers: [provideHttpClient()]}).catch(error => console.error(error));
