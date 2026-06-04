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
      <div><span class="eyebrow">DECISION INTELLIGENCE</span><h1>Strategic Risk Radar</h1></div>
      <button (click)="loadAll()">Refresh data</button>
    </header>

    <main>
      <section class="cards" *ngIf="overview">
        <article><label>Ingestion runs</label><strong>{{overview.total_runs}}</strong></article>
        <article><label>Documents</label><strong>{{overview.total_documents}}</strong></article>
        <article><label>New documents</label><strong>{{overview.total_inserted}}</strong></article>
        <article class="warning"><label>Runs with errors</label><strong>{{overview.runs_with_errors}}</strong></article>
      </section>

      <nav>
        <button *ngFor="let item of tabs" [class.active]="tab===item" (click)="tab=item">{{item}}</button>
      </nav>

      <section class="panel" *ngIf="tab==='Documents'">
        <div class="filters">
          <input [(ngModel)]="search" placeholder="Search titles and summaries">
          <select [(ngModel)]="source"><option value="">All sources</option><option *ngFor="let s of sourceNames">{{s}}</option></select>
          <button (click)="loadDocuments()">Search</button>
        </div>
        <div class="documents">
          <article *ngFor="let d of documents">
            <div><span class="source">{{d.source_id}}</span><span class="keywords">{{d.keywords}}</span></div>
            <h2><a [href]="d.url" target="_blank">{{d.title}}</a></h2>
            <p>{{d.summary | slice:0:300}}</p>
            <small>{{d.published_at || d.first_seen_at | date:'medium'}}</small>
          </article>
        </div>
      </section>

      <section class="panel" *ngIf="tab==='Runs'">
        <h2>Recent ingestion runs</h2>
        <table><thead><tr><th>Started</th><th>Status</th><th>Retrieved</th><th>Matched</th><th>Inserted</th><th>Duplicates</th><th>Errors</th></tr></thead>
        <tbody><tr *ngFor="let r of runs"><td>{{r.started_at | date:'medium'}}</td><td><span class="status">{{r.status}}</span></td><td>{{r.total_retrieved}}</td><td>{{r.total_matched}}</td><td>{{r.total_inserted}}</td><td>{{r.total_duplicates}}</td><td>{{r.error_count}}</td></tr></tbody></table>
      </section>

      <section class="panel" *ngIf="tab==='Sources'">
        <h2>Source execution windows</h2>
        <table><thead><tr><th>Source</th><th>Status</th><th>Window start</th><th>Window end</th><th>Retrieved</th><th>Inserted</th><th>Duration</th></tr></thead>
        <tbody><tr *ngFor="let s of sources"><td>{{s.source_id}}</td><td><span class="status">{{s.status}}</span></td><td>{{s.window_start | date:'short'}}</td><td>{{s.window_end | date:'short'}}</td><td>{{s.retrieved_count}}</td><td>{{s.inserted_count}}</td><td>{{s.duration_ms}} ms</td></tr></tbody></table>
      </section>

      <section class="panel" *ngIf="tab==='Keywords'">
        <h2>Keyword performance</h2>
        <table><thead><tr><th>Source</th><th>Keyword</th><th>Retrieved</th><th>Matched</th><th>Inserted</th><th>Duplicates</th></tr></thead>
        <tbody><tr *ngFor="let k of keywords"><td>{{k.source_id}}</td><td>{{k.keyword}}</td><td>{{k.retrieved_count}}</td><td>{{k.matched_count}}</td><td>{{k.inserted_count}}</td><td>{{k.duplicate_count}}</td></tr></tbody></table>
      </section>
    </main>`,
})
class App implements OnInit {
  tabs = ['Documents', 'Runs', 'Sources', 'Keywords']; tab = 'Documents';
  overview: any; runs: any[] = []; sources: any[] = []; keywords: any[] = []; documents: any[] = [];
  search = ''; source = ''; sourceNames: string[] = [];
  constructor(private http: HttpClient) {}
  ngOnInit() { this.loadAll(); }
  loadAll() {
    this.http.get('/api/overview').subscribe(v => this.overview = v);
    this.http.get<any[]>('/api/runs').subscribe(v => this.runs = v);
    this.http.get<any[]>('/api/sources').subscribe(v => { this.sources = v; this.sourceNames = [...new Set(v.map(x => x.source_id))]; });
    this.http.get<any[]>('/api/keywords').subscribe(v => this.keywords = v);
    this.loadDocuments();
  }
  loadDocuments() {
    const q = new URLSearchParams({search: this.search, source: this.source});
    this.http.get<any[]>('/api/documents?' + q).subscribe(v => this.documents = v);
  }
}

bootstrapApplication(App, {providers: [provideHttpClient()]});

