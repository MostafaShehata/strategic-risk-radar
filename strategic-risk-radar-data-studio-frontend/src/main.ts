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
      <div>
        <span class="eyebrow">DECISION INTELLIGENCE</span>
        <h1>Strategic Risk Radar</h1>
        <p>Operational view for ingestion, enrichment, topics, risk signals, and evidence.</p>
      </div>
      <button (click)="loadAll()">Refresh data</button>
    </header>

    <main>
      <section class="cards" *ngIf="overview">
        <article><label>Raw documents</label><strong>{{overview.total_documents}}</strong></article>
        <article><label>Enriched documents</label><strong>{{overview.enriched_documents}}</strong></article>
        <article><label>Strategic topics</label><strong>{{overview.topics}}</strong></article>
        <article><label>KPI impacts</label><strong>{{overview.kpi_impacts}}</strong></article>
        <article><label>Pending enrichment</label><strong>{{overview.pending_enrichment}}</strong></article>
      </section>

      <nav>
        <button *ngFor="let item of tabs" [class.active]="tab===item" (click)="tab=item">{{item}}</button>
      </nav>

      <section *ngIf="tab==='System Status'" class="two-column">
        <aside class="panel run-list">
          <div class="section-heading">
            <div><span class="eyebrow dark">INGESTION</span><h2>Source runs</h2></div>
          </div>
          <div class="filters compact">
            <select [(ngModel)]="runSourceType" (change)="loadRuns()">
              <option value="">All source types</option>
              <option *ngFor="let t of sourceTypes">{{t}}</option>
            </select>
            <select [(ngModel)]="runStatus" (change)="loadRuns()">
              <option value="">All statuses</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="completed_with_errors">Completed with errors</option>
            </select>
          </div>
          <button class="run-card" *ngFor="let run of runs" [class.selected]="selectedRunId===run.id" (click)="selectRun(run.id)">
            <div><strong>{{run.source_id || 'source job'}}</strong><span class="badge" [class.bad]="run.error_count">{{run.status}}</span></div>
            <small class="mono">Run {{shortId(run.id)}} / Source run {{run.source_run_id}}</small>
            <small>{{run.source_type}} - {{run.started_at | date:'medium'}}</small>
            <div class="mini-metrics"><span>{{run.total_retrieved}} retrieved</span><span>{{run.total_inserted}} new</span><span>{{run.error_count}} errors</span></div>
          </button>
        </aside>

        <section class="panel run-detail" *ngIf="runDetail?.run; else selectIngestionPrompt">
          <div class="section-heading">
            <div><span class="eyebrow dark">INGESTION RUN DETAIL</span><h2 class="mono">{{runDetail.run.id}}</h2></div>
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
              <div><h3>{{source.source_id}}</h3><small class="mono">Source run id {{source.id}}</small></div>
              <span class="badge" [class.bad]="source.status==='error'">{{source.status}}</span>
            </div>
            <small>{{source.window_start | date:'medium'}} to {{source.window_end | date:'medium'}}</small>
            <div class="source-stats">
              <span><b>{{source.request_count}}</b> requests</span><span><b>{{source.retrieved_count}}</b> retrieved</span>
              <span><b>{{source.matched_count}}</b> matched</span><span><b>{{source.inserted_count}}</b> inserted</span>
              <span><b>{{source.duplicate_count}}</b> duplicates</span><span><b>{{source.duration_ms}} ms</b> duration</span>
            </div>
            <p class="error" *ngIf="source.error_message && source.status!=='skipped'"><strong>Source warnings:</strong><br>{{source.error_message}}</p>
            <table><thead><tr><th>Keyword</th><th>Requests</th><th>Retrieved</th><th>Matched</th><th>Inserted</th><th>Duplicates</th></tr></thead>
              <tbody><tr *ngFor="let keyword of source.keywords"><td><strong>{{keyword.keyword}}</strong></td><td>{{keyword.request_count}}</td><td>{{keyword.retrieved_count}}</td><td>{{keyword.matched_count}}</td><td>{{keyword.inserted_count}}</td><td>{{keyword.duplicate_count}}</td></tr></tbody>
            </table>
          </article>
        </section>
        <ng-template #selectIngestionPrompt><section class="panel empty">Select an ingestion run to view source and keyword metrics.</section></ng-template>

        <aside class="panel run-list">
          <div class="section-heading">
            <div><span class="eyebrow dark">ENRICHMENT</span><h2>Agent runs</h2></div>
          </div>
          <div class="filters compact">
            <select [(ngModel)]="enrichmentRunStatus" (change)="loadEnrichmentRuns()">
              <option value="">All statuses</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="completed_with_errors">Completed with errors</option>
            </select>
          </div>
          <button class="run-card" *ngFor="let run of enrichmentRuns" [class.selected]="selectedEnrichmentRunId===run.id" (click)="selectEnrichmentRun(run.id)">
            <div><strong>Enrichment cycle</strong><span class="badge" [class.bad]="run.failed_count">{{run.status}}</span></div>
            <small class="mono">Run {{shortId(run.id)}}</small>
            <small>{{run.started_at | date:'medium'}} / {{run.duration_seconds}}s</small>
            <div class="mini-metrics"><span>{{run.processed_count}} processed</span><span>{{run.success_count}} success</span><span>{{run.failed_count}} failed</span></div>
          </button>
        </aside>

        <section class="panel run-detail" *ngIf="enrichmentRunDetail?.run; else selectEnrichmentPrompt">
          <div class="section-heading">
            <div><span class="eyebrow dark">ENRICHMENT RUN DETAIL</span><h2 class="mono">{{enrichmentRunDetail.run.id}}</h2></div>
            <span class="badge large" [class.bad]="enrichmentRunDetail.run.failed_count">{{enrichmentRunDetail.run.status}}</span>
          </div>
          <div class="summary-strip">
            <span><label>Processed</label><strong>{{enrichmentRunDetail.run.processed_count}}</strong></span>
            <span><label>Success</label><strong>{{enrichmentRunDetail.run.success_count}}</strong></span>
            <span><label>Failed</label><strong>{{enrichmentRunDetail.run.failed_count}}</strong></span>
            <span><label>Model</label><strong class="small-strong">{{enrichmentRunDetail.run.model_name}}</strong></span>
          </div>
          <table><thead><tr><th>Article</th><th>Source</th><th>Risk</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              <tr *ngFor="let item of enrichmentRunDetail.items" (click)="selectEnrichedItem(item.id)" class="clickable">
                <td>{{item.title}}</td><td>{{item.source_id}}</td><td><span class="risk-pill" [ngClass]="riskClass(item.risk_level)">{{item.risk_score}} {{item.risk_level}}</span></td><td>{{item.enrichment_status}}</td><td>{{item.created_at | date:'medium'}}</td>
              </tr>
            </tbody>
          </table>
        </section>
        <ng-template #selectEnrichmentPrompt><section class="panel empty">Select an enrichment run to see agent output for that cycle.</section></ng-template>
      </section>

      <section class="workspace" *ngIf="tab==='Enriched Intelligence'">
        <section class="panel">
          <div class="section-heading">
            <div><span class="eyebrow dark">KPI RISK DASHBOARD</span><h2>UAE operational impact</h2></div>
            <span class="badge large">{{enrichedItems.length}} shown</span>
          </div>
          <div class="kpi-grid">
            <article *ngFor="let kpi of kpis" [class]="riskClass(levelFromScore(kpi.highest_risk_score))">
              <label>{{kpi.kpi_name}}</label>
              <strong>{{kpi.highest_risk_score}}</strong>
              <span>{{kpi.article_count}} linked articles</span>
              <small>Critical {{kpi.critical_count}} / High {{kpi.high_count}} / Medium {{kpi.medium_count}}</small>
            </article>
          </div>

          <div class="section-heading subhead">
            <div><span class="eyebrow dark">ENRICHED NEWS</span><h2>Risk-scored articles</h2></div>
          </div>
          <div class="filters">
            <input [(ngModel)]="enrichedSearch" (keyup.enter)="loadEnrichedItems()" placeholder="Search title, summary, body">
            <select [(ngModel)]="enrichedSource"><option value="">All sources</option><option *ngFor="let s of enrichmentOptions.sources">{{s}}</option></select>
            <select [(ngModel)]="riskLevel"><option value="">All risk levels</option><option *ngFor="let r of enrichmentOptions.risk_levels">{{r}}</option></select>
            <select [(ngModel)]="riskDomain"><option value="">All domains</option><option *ngFor="let d of enrichmentOptions.domains">{{d}}</option></select>
            <select [(ngModel)]="enrichedKeyword"><option value="">All keywords</option><option *ngFor="let k of keywords">{{k}}</option></select>
            <input class="score-input" type="number" min="0" max="100" [(ngModel)]="minScore" placeholder="Min score">
            <button (click)="loadEnrichedItems()">Apply</button>
          </div>
          <div class="enriched-grid">
            <article *ngFor="let item of enrichedItems" [class.selected]="selectedEnrichedItem?.item?.id===item.id" (click)="selectEnrichedItem(item.id)">
              <div class="article-top">
                <span class="source">{{item.source_id}}</span>
                <span class="risk-pill" [ngClass]="riskClass(item.risk_level)">{{item.risk_score}} {{item.risk_level}}</span>
              </div>
              <h3>{{item.title}}</h3>
              <p>{{item.summary | slice:0:240}}</p>
              <div class="chips">
                <span *ngFor="let d of asList(item.risk_domains)">{{d}}</span>
                <span *ngIf="item.topic_title">Topic: {{item.topic_title}}</span>
              </div>
              <small>{{item.publication_date || item.created_at | date:'medium'}} / {{item.enrichment_status}} / {{item.body_source}}</small>
            </article>
          </div>
        </section>

        <aside class="panel detail-panel" *ngIf="selectedEnrichedItem?.item; else selectArticlePrompt">
          <div class="section-heading">
            <div><span class="eyebrow dark">AGENT OUTPUT</span><h2>{{selectedEnrichedItem.item.title}}</h2></div>
          </div>
          <div class="risk-hero" [ngClass]="riskClass(selectedEnrichedItem.item.risk_level)">
            <strong>{{selectedEnrichedItem.item.risk_score}}</strong>
            <span>{{selectedEnrichedItem.item.risk_level}} risk</span>
            <small>{{selectedEnrichedItem.item.risk_reason}}</small>
          </div>
          <dl class="meta-grid">
            <div><dt>Enriched ID</dt><dd class="mono">{{selectedEnrichedItem.item.id}}</dd></div>
            <div><dt>Raw item ID</dt><dd class="mono">{{selectedEnrichedItem.item.raw_news_item_id}}</dd></div>
            <div><dt>Topic</dt><dd>{{selectedEnrichedItem.item.topic_title || 'No topic'}}</dd></div>
            <div><dt>Language</dt><dd>{{selectedEnrichedItem.item.language}}</dd></div>
            <div><dt>Body source</dt><dd>{{selectedEnrichedItem.item.body_source}}</dd></div>
            <div><dt>Confidence</dt><dd>{{selectedEnrichedItem.item.confidence_score}}</dd></div>
          </dl>

          <h3>Normalize Agent</h3>
          <p class="body-preview">{{selectedEnrichedItem.item.normalized_body | slice:0:900}}</p>
          <div class="fetch-list" *ngIf="selectedEnrichedItem.content_fetches?.length">
            <strong>Firecrawler attempts</strong>
            <div *ngFor="let fetch of selectedEnrichedItem.content_fetches">
              <span class="badge" [class.bad]="fetch.status!=='success'">{{fetch.status}}</span>
              <small>{{fetch.fetcher}} / body {{fetch.body_length}} chars / {{fetch.created_at | date:'medium'}}</small>
            </div>
          </div>

          <h3>Entity Extraction Agent</h3>
          <div class="entity-groups">
            <div *ngFor="let group of groupedEntities()">
              <strong>{{group.type}}</strong>
              <span *ngFor="let entity of group.items">{{entity.name}} <small *ngIf="entity.code">({{entity.code}})</small></span>
            </div>
          </div>

          <h3>Geo / Transport Resolver and Path Impact Agent</h3>
          <table *ngIf="selectedEnrichedItem.path_impacts?.length; else noPaths">
            <thead><tr><th>Path</th><th>Impact</th><th>Level</th><th>Reason</th></tr></thead>
            <tbody><tr *ngFor="let p of selectedEnrichedItem.path_impacts"><td>{{p.path_code}}</td><td>{{p.impact_type}}</td><td>{{p.impact_level}}</td><td>{{p.reason}}</td></tr></tbody>
          </table>
          <ng-template #noPaths><p class="info">No route/path impact was detected for this article.</p></ng-template>

          <h3>KPI Impact Agent</h3>
          <table *ngIf="selectedEnrichedItem.kpi_impacts?.length; else noKpis">
            <thead><tr><th>KPI</th><th>Risk</th><th>Impact</th><th>Evidence</th></tr></thead>
            <tbody>
              <tr *ngFor="let k of selectedEnrichedItem.kpi_impacts">
                <td>{{k.kpi_name}}</td>
                <td><span class="risk-pill" [ngClass]="riskClass(k.risk_level)">{{k.risk_score}} {{k.risk_level}}</span></td>
                <td>{{k.impact_summary}}</td>
                <td>{{k.evidence}}</td>
              </tr>
            </tbody>
          </table>
          <ng-template #noKpis><p class="info">No KPI impact was detected for this article.</p></ng-template>

          <h3>Final Validator</h3>
          <p><span class="badge" [class.bad]="selectedEnrichedItem.item.enrichment_status==='needs_review'">{{selectedEnrichedItem.item.enrichment_status}}</span></p>
        </aside>
        <ng-template #selectArticlePrompt><aside class="panel empty">Select an enriched article to inspect every agent output.</aside></ng-template>
      </section>

      <section class="workspace" *ngIf="tab==='Topics'">
        <section class="panel">
          <div class="section-heading"><div><span class="eyebrow dark">STRATEGIC TOPIC BOARD</span><h2>Situations affecting UAE responsibilities</h2></div></div>
          <div class="filters">
            <input [(ngModel)]="topicSearch" (keyup.enter)="loadTopics()" placeholder="Search topics">
            <select [(ngModel)]="topicRiskLevel"><option value="">All risk levels</option><option *ngFor="let r of enrichmentOptions.risk_levels">{{r}}</option></select>
            <select [(ngModel)]="topicDomain"><option value="">All domains</option><option *ngFor="let d of enrichmentOptions.domains">{{d}}</option></select>
            <button (click)="loadTopics()">Apply</button>
          </div>
          <div class="topic-list">
            <button class="topic-card" *ngFor="let topic of topics" [class.selected]="selectedTopic?.topic?.id===topic.id" (click)="selectTopic(topic.id)">
              <div><strong>{{topic.title}}</strong><span class="risk-pill" [ngClass]="riskClass(topic.risk_level)">{{topic.risk_score}} {{topic.risk_level}}</span></div>
              <small class="mono">Topic {{shortId(topic.id)}} / {{topic.article_count}} articles / {{topic.event_type || 'event'}}</small>
              <p>{{topic.uae_impact || topic.summary || 'Strategic topic awaiting UAE impact summary.'}}</p>
              <div class="chips"><span *ngFor="let k of asList(topic.affected_kpis)">{{k}}</span><span *ngFor="let d of asList(topic.primary_domains)">{{d}}</span></div>
            </button>
          </div>
        </section>

        <aside class="panel detail-panel" *ngIf="selectedTopic?.topic; else selectTopicPrompt">
          <div class="section-heading">
            <div><span class="eyebrow dark">TOPIC DETAIL</span><h2>{{selectedTopic.topic.title}}</h2></div>
            <span class="badge large">{{selectedTopic.articles.length}} articles</span>
          </div>
          <p>{{selectedTopic.topic.summary || 'No generated summary yet.'}}</p>
          <div class="uae-impact">
            <strong>Expected UAE impact</strong>
            <p>{{selectedTopic.topic.uae_impact || 'No UAE impact summary yet.'}}</p>
          </div>
          <dl class="meta-grid">
            <div><dt>Topic ID</dt><dd class="mono">{{selectedTopic.topic.id}}</dd></div>
            <div><dt>Topic key</dt><dd>{{selectedTopic.topic.topic_key || selectedTopic.topic.signature || 'No key'}}</dd></div>
            <div><dt>Event type</dt><dd>{{selectedTopic.topic.event_type || 'Unknown'}}</dd></div>
            <div><dt>Risk</dt><dd>{{selectedTopic.topic.risk_score}} / {{selectedTopic.topic.risk_level}}</dd></div>
            <div><dt>Status</dt><dd>{{selectedTopic.topic.status}}</dd></div>
          </dl>
          <div class="chips"><span *ngFor="let k of asList(selectedTopic.topic.affected_kpis)">{{k}}</span></div>
          <table>
            <thead><tr><th>Article</th><th>Risk</th><th>Similarity</th><th>Primary</th></tr></thead>
            <tbody>
              <tr *ngFor="let article of selectedTopic.articles" (click)="selectEnrichedItem(article.id); tab='Enriched Intelligence'" class="clickable">
                <td>{{article.title}}</td><td>{{article.risk_score}} {{article.risk_level}}</td><td>{{article.similarity_score}}</td><td>{{article.is_primary_article ? 'Yes' : 'No'}}</td>
              </tr>
            </tbody>
          </table>
        </aside>
        <ng-template #selectTopicPrompt><aside class="panel empty">Select a topic to view clustered articles.</aside></ng-template>
      </section>

      <section class="panel" *ngIf="tab==='Raw Documents'">
        <div class="section-heading"><div><span class="eyebrow dark">RAW EVIDENCE</span><h2>Browse ingested documents</h2></div></div>
        <div class="filters">
          <input [(ngModel)]="search" (keyup.enter)="loadDocuments()" placeholder="Search titles and summaries">
          <select [(ngModel)]="source"><option value="">All sources</option><option *ngFor="let s of sourceNames">{{s}}</option></select>
          <select [(ngModel)]="keyword"><option value="">All keywords</option><option *ngFor="let k of keywords">{{k}}</option></select>
          <button (click)="loadDocuments()">Search</button>
        </div>
        <div class="documents">
          <article *ngFor="let d of documents">
            <div><span class="source">{{d.source_id}}</span><span class="keywords">{{d.keywords}}</span></div>
            <h3><a [href]="d.url" target="_blank" rel="noopener">{{d.title}}</a></h3>
            <p>{{d.summary | slice:0:300}}</p>
            <small>{{d.published_at || d.first_seen_at | date:'medium'}} / {{d.processing_status}}</small>
          </article>
        </div>
      </section>
    </main>`,
})
class App implements OnInit {
  tabs = ['System Status', 'Enriched Intelligence', 'Topics', 'Raw Documents'];
  tab = 'System Status';
  overview: any;
  runs: any[] = [];
  enrichmentRuns: any[] = [];
  documents: any[] = [];
  enrichedItems: any[] = [];
  topics: any[] = [];
  kpis: any[] = [];
  runDetail: any;
  enrichmentRunDetail: any;
  selectedEnrichedItem: any;
  selectedTopic: any;
  selectedRunId = '';
  selectedEnrichmentRunId = '';
  search = '';
  source = '';
  keyword = '';
  runSourceType = '';
  runStatus = '';
  enrichmentRunStatus = '';
  enrichedSearch = '';
  enrichedSource = '';
  riskLevel = '';
  riskDomain = '';
  enrichedKeyword = '';
  minScore = 0;
  topicSearch = '';
  topicRiskLevel = '';
  topicDomain = '';
  sourceNames: string[] = [];
  sourceTypes: string[] = [];
  keywords: string[] = [];
  enrichmentOptions: any = {sources: [], domains: [], risk_levels: [], statuses: []};

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.loadAll();
  }

  loadAll() {
    this.http.get('/api/overview').subscribe(v => this.overview = v);
    this.http.get<any[]>('/api/source-types').subscribe(v => this.sourceTypes = v.map(x => x.source_type));
    this.http.get<any[]>('/api/document-keywords').subscribe(v => this.keywords = v.map(x => x.keyword));
    this.http.get<any>('/api/enrichment/filter-options').subscribe(v => this.enrichmentOptions = v);
    this.loadRuns();
    this.loadEnrichmentRuns();
    this.loadDocuments();
    this.loadEnrichedItems();
    this.loadTopics();
    this.loadKpis();
  }

  loadRuns() {
    const q = new URLSearchParams({source_type: this.runSourceType, status: this.runStatus});
    this.http.get<any[]>('/api/runs?' + q).subscribe(v => {
      this.runs = v;
      if (v.length && (!this.selectedRunId || !v.some(run => run.id === this.selectedRunId))) this.selectRun(v[0].id);
    });
  }

  selectRun(id: string) {
    this.selectedRunId = id;
    this.http.get('/api/runs/' + id).subscribe(v => this.runDetail = v);
  }

  loadEnrichmentRuns() {
    const q = new URLSearchParams({status: this.enrichmentRunStatus});
    this.http.get<any[]>('/api/enrichment/runs?' + q).subscribe(v => {
      this.enrichmentRuns = v;
      if (v.length && (!this.selectedEnrichmentRunId || !v.some(run => run.id === this.selectedEnrichmentRunId))) this.selectEnrichmentRun(v[0].id);
    });
  }

  selectEnrichmentRun(id: string) {
    this.selectedEnrichmentRunId = id;
    this.http.get('/api/enrichment/runs/' + id).subscribe(v => this.enrichmentRunDetail = v);
  }

  loadDocuments() {
    const q = new URLSearchParams({search: this.search, source: this.source, keyword: this.keyword});
    this.http.get<any[]>('/api/documents?' + q).subscribe(v => {
      this.documents = v;
      this.sourceNames = [...new Set(v.map(x => x.source_id))];
    });
  }

  loadEnrichedItems() {
    const q = new URLSearchParams({
      search: this.enrichedSearch,
      source: this.enrichedSource,
      risk_level: this.riskLevel,
      domain: this.riskDomain,
      keyword: this.enrichedKeyword,
      min_score: String(this.minScore || 0),
    });
    this.http.get<any[]>('/api/enrichment/items?' + q).subscribe(v => {
      this.enrichedItems = v;
      if (v.length && !this.selectedEnrichedItem) this.selectEnrichedItem(v[0].id);
    });
    this.loadKpis();
  }

  loadKpis() {
    const q = new URLSearchParams({source: this.enrichedSource, risk_level: this.riskLevel});
    this.http.get<any[]>('/api/enrichment/kpis?' + q).subscribe(v => this.kpis = v);
  }

  selectEnrichedItem(id: string) {
    this.http.get<any>('/api/enrichment/items/' + id).subscribe(v => this.selectedEnrichedItem = v);
  }

  loadTopics() {
    const q = new URLSearchParams({search: this.topicSearch, risk_level: this.topicRiskLevel, domain: this.topicDomain});
    this.http.get<any[]>('/api/enrichment/topics?' + q).subscribe(v => {
      this.topics = v;
      if (v.length && !this.selectedTopic) this.selectTopic(v[0].id);
    });
  }

  selectTopic(id: string) {
    this.http.get<any>('/api/enrichment/topics/' + id).subscribe(v => this.selectedTopic = v);
  }

  asList(value: any): string[] {
    if (!value) return [];
    if (Array.isArray(value)) return value.map(x => String(x));
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed.map(x => String(x)) : [String(value)];
    } catch {
      return [String(value)];
    }
  }

  groupedEntities(): any[] {
    const entities = this.selectedEnrichedItem?.entities || [];
    const groups = new Map<string, any[]>();
    for (const entity of entities) {
      if (!groups.has(entity.entity_type)) groups.set(entity.entity_type, []);
      groups.get(entity.entity_type)?.push(entity);
    }
    return [...groups.entries()].map(([type, items]) => ({type, items}));
  }

  riskClass(level: string): string {
    return 'risk-' + String(level || 'low').toLowerCase();
  }

  levelFromScore(score: number): string {
    if (score >= 75) return 'critical';
    if (score >= 50) return 'high';
    if (score >= 25) return 'medium';
    return 'low';
  }

  shortId(id: string): string {
    return id ? id.slice(0, 8) : '';
  }
}

bootstrapApplication(App, {providers: [provideHttpClient()]}).catch(error => console.error(error));
