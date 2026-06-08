import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { RadarApiService } from './radar-api.service';
import { MetricCardComponent } from './components/metric-card.component';
import { PipelineBoardComponent } from './components/pipeline-board.component';
import { RadarMapComponent } from './components/radar-map.component';
import { SourceHealthComponent } from './components/source-health.component';
import { StatusPillComponent } from './components/status-pill.component';
import { TopicBoardComponent } from './components/topic-board.component';
import { riskClass, shortId } from './shared/ui-utils';

type ViewName = 'Command Center' | 'Topics & KPI' | 'Pipelines' | 'Raw Documents' | 'Enriched Intelligence';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MetricCardComponent,
    PipelineBoardComponent,
    RadarMapComponent,
    SourceHealthComponent,
    StatusPillComponent,
    TopicBoardComponent,
  ],
  template: `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="crest">ICP</span>
          <div>
            <strong>Strategic Radar</strong>
            <small>Decision Intelligence</small>
          </div>
        </div>
        <button *ngFor="let item of views" [class.active]="view === item" (click)="setView(item)">
          <span></span>{{ item }}
        </button>
        <div class="system-card">
          <small>RAG status</small>
          <strong>{{ command?.rag?.status || 'loading' }}</strong>
          <span>{{ command?.rag?.points_count || 0 }} indexed chunks</span>
        </div>
      </aside>

      <main>
        <header class="hero">
          <div>
            <span class="eyebrow">UAE ICP COMMAND CENTER</span>
            <h1>Strategic Risk Radar</h1>
            <p>Live operational intelligence across news ingestion, enrichment agents, strategic topics, KPI impact, and RAG readiness.</p>
          </div>
          <div class="hero-actions">
            <span>{{ now | date:'medium':'Asia/Dubai' }}</span>
            <button (click)="refresh()">Refresh</button>
          </div>
        </header>

        <section class="metric-grid">
          <radar-metric-card label="Raw documents" [value]="overview.total_documents || 0" hint="ingested evidence"></radar-metric-card>
          <radar-metric-card label="Enriched documents" [value]="overview.enriched_documents || 0" hint="agent processed"></radar-metric-card>
          <radar-metric-card label="Strategic topics" [value]="overview.topics || 0" hint="LLM topic board"></radar-metric-card>
          <radar-metric-card label="KPI impacts" [value]="overview.kpi_impacts || 0" hint="business impact rows"></radar-metric-card>
          <radar-metric-card label="Pending" [value]="overview.pending_enrichment || overview.pending_documents || 0" hint="waiting enrichment" tone="warn"></radar-metric-card>
        </section>

        <section *ngIf="view === 'Command Center'" class="command-grid">
          <radar-map [topTopic]="topics[0]" [activeTopics]="topics.length"></radar-map>
          <radar-source-health [sources]="sources"></radar-source-health>
          <radar-topic-board [topics]="topics" (openTopic)="openTopic($event)"></radar-topic-board>
          <radar-pipeline-board [ingestionRuns]="ingestionRuns" [enrichmentRuns]="enrichmentRuns"></radar-pipeline-board>

          <section class="glass-card wide">
            <div class="panel-heading">
              <div><span class="eyebrow">LATEST INTELLIGENCE</span><h2>High signal enriched news</h2></div>
            </div>
            <div class="intel-list">
              <button *ngFor="let item of latestItems" (click)="openEnriched(item)">
                <radar-status-pill mode="risk" [label]="item.risk_level"></radar-status-pill>
                <div>
                  <strong>{{ item.title }}</strong>
                  <small>{{ item.source_id }} / {{ item.topic_title || 'no topic' }} / {{ item.publication_date | date:'medium' }}</small>
                </div>
                <b>{{ item.risk_score || 0 }}</b>
              </button>
            </div>
          </section>
        </section>

        <section *ngIf="view === 'Topics & KPI'" class="two-pane">
          <section class="glass-card">
            <div class="panel-heading"><div><span class="eyebrow">TOPICS</span><h2>Strategic board</h2></div></div>
            <button class="topic-row" *ngFor="let topic of topics" (click)="openTopic(topic)" [class.selected]="selectedTopic?.id === topic.id">
              <div><strong>{{ topic.title }}</strong><small>{{ topic.uae_impact || topic.summary }}</small></div>
              <radar-status-pill mode="risk" [label]="topic.risk_level"></radar-status-pill>
            </button>
          </section>
          <section class="glass-card detail-card">
            <ng-container *ngIf="topicDetail?.topic; else noTopic">
              <div class="panel-heading">
                <div><span class="eyebrow">UAE IMPACT</span><h2>{{ topicDetail.topic.title }}</h2></div>
                <radar-status-pill mode="risk" [label]="topicDetail.topic.risk_level"></radar-status-pill>
              </div>
              <p class="lead">{{ topicDetail.topic.uae_impact || topicDetail.topic.summary }}</p>
              <h3>KPI impact</h3>
              <div class="kpi-grid">
                <article *ngFor="let kpi of topicDetail.kpis">
                  <strong>{{ kpi.kpi_name }}</strong>
                  <b>{{ kpi.highest_risk_score }}</b>
                  <small>{{ kpi.impact_summary }}</small>
                </article>
              </div>
              <h3>Related articles</h3>
              <button class="article-row" *ngFor="let article of topicDetail.articles" (click)="openEnriched(article)">
                <span>{{ article.title }}</span>
                <radar-status-pill mode="risk" [label]="article.risk_level"></radar-status-pill>
              </button>
            </ng-container>
            <ng-template #noTopic><p class="empty">Select a strategic topic to inspect KPI impact and evidence.</p></ng-template>
          </section>
        </section>

        <section *ngIf="view === 'Pipelines'" class="two-pane">
          <section class="glass-card">
            <div class="panel-heading"><div><span class="eyebrow">INGESTION EXECUTION</span><h2>Source runs</h2></div></div>
            <button class="run-row" *ngFor="let run of ingestionRuns" (click)="selectRun(run.id)">
              <radar-status-pill [label]="run.status"></radar-status-pill>
              <div><strong>{{ run.source_id || shortId(run.id) }}</strong><small>{{ run.total_retrieved }} retrieved / {{ run.total_inserted }} inserted</small></div>
            </button>
          </section>
          <section class="glass-card detail-card">
            <ng-container *ngIf="runDetail?.run; else noRun">
              <div class="panel-heading"><div><span class="eyebrow">RUN DETAIL</span><h2>{{ shortId(runDetail.run.id) }}</h2></div><radar-status-pill [label]="runDetail.run.status"></radar-status-pill></div>
              <div class="stats-line"><span>{{ runDetail.run.total_retrieved }} retrieved</span><span>{{ runDetail.run.total_inserted }} inserted</span><span>{{ runDetail.run.error_count }} errors</span></div>
              <article class="source-detail" *ngFor="let source of runDetail.sources">
                <strong>{{ source.source_id }}</strong>
                <small>{{ source.window_start | date:'short' }} to {{ source.window_end | date:'short' }}</small>
                <p *ngIf="source.error_message">{{ source.error_message }}</p>
                <table><tr><th>Keyword</th><th>Retrieved</th><th>Inserted</th></tr><tr *ngFor="let kw of source.keywords"><td>{{ kw.keyword }}</td><td>{{ kw.retrieved_count }}</td><td>{{ kw.inserted_count }}</td></tr></table>
              </article>
            </ng-container>
            <ng-template #noRun><p class="empty">Select a run for source and keyword metrics.</p></ng-template>
          </section>
        </section>

        <section *ngIf="view === 'Raw Documents'" class="workbench">
          <section class="glass-card">
            <div class="panel-heading"><div><span class="eyebrow">RAW DATA</span><h2>Ingested documents</h2></div></div>
            <div class="filters">
              <input [(ngModel)]="documentSearch" placeholder="Search raw documents" (keyup.enter)="loadDocuments()" />
              <button (click)="loadDocuments()">Search</button>
            </div>
            <button class="article-row" *ngFor="let doc of documents" (click)="openDocument(doc)">
              <span>{{ doc.title }}</span><small>{{ doc.source_id }} / {{ doc.processing_status }}</small>
            </button>
          </section>
          <section class="glass-card detail-card">
            <ng-container *ngIf="documentDetail?.document; else noDoc">
              <span class="eyebrow">{{ documentDetail.document.source_id }}</span>
              <h2>{{ documentDetail.document.title }}</h2>
              <a [href]="documentDetail.document.url" target="_blank">Open source</a>
              <p>{{ documentDetail.document.summary || documentDetail.document.body || 'No body available.' }}</p>
              <h3>Fetch attempts</h3>
              <div class="small-row" *ngFor="let fetch of documentDetail.content_fetches">{{ fetch.status }} / {{ fetch.fetcher }} / {{ fetch.body_length }} chars</div>
            </ng-container>
            <ng-template #noDoc><p class="empty">Select a raw document to inspect evidence and crawler attempts.</p></ng-template>
          </section>
        </section>

        <section *ngIf="view === 'Enriched Intelligence'" class="workbench">
          <section class="glass-card">
            <div class="panel-heading"><div><span class="eyebrow">ENRICHED DATA</span><h2>Agent output</h2></div></div>
            <div class="filters">
              <input [(ngModel)]="enrichedSearch" placeholder="Search enriched intelligence" (keyup.enter)="loadEnriched()" />
              <select [(ngModel)]="riskLevel"><option value="">All risk</option><option>critical</option><option>high</option><option>medium</option><option>low</option><option>unknown</option></select>
              <button (click)="loadEnriched()">Filter</button>
            </div>
            <button class="article-row" *ngFor="let item of enrichedItems" (click)="openEnriched(item)">
              <span>{{ item.title }}</span><radar-status-pill mode="risk" [label]="item.risk_level"></radar-status-pill>
            </button>
          </section>
          <section class="glass-card detail-card">
            <ng-container *ngIf="enrichedDetail?.item; else noEnriched">
              <div class="panel-heading"><div><span class="eyebrow">{{ enrichedDetail.item.source_id }}</span><h2>{{ enrichedDetail.item.title }}</h2></div><radar-status-pill mode="risk" [label]="enrichedDetail.item.risk_level"></radar-status-pill></div>
              <p class="lead">{{ enrichedDetail.item.risk_reason || enrichedDetail.item.summary }}</p>
              <div class="chip-row"><span *ngFor="let domain of enrichedDetail.item.risk_domains">{{ domain }}</span></div>
              <h3>Entities</h3>
              <div class="small-row" *ngFor="let entity of enrichedDetail.entities">{{ entity.entity_type }}: {{ entity.normalized_name || entity.name }} {{ entity.code }}</div>
              <h3>KPI impacts</h3>
              <article class="kpi-row" *ngFor="let kpi of enrichedDetail.kpi_impacts"><strong>{{ kpi.kpi_name }}</strong><b>{{ kpi.risk_score }}</b><p>{{ kpi.impact_summary }}</p></article>
              <h3>Path impacts</h3>
              <div class="small-row" *ngFor="let path of enrichedDetail.path_impacts">{{ path.path_code }} / {{ path.impact_type }} / {{ path.reason }}</div>
            </ng-container>
            <ng-template #noEnriched><p class="empty">Select enriched intelligence to inspect all agent output.</p></ng-template>
          </section>
        </section>
      </main>
    </div>
  `,
})
export class AppComponent implements OnInit {
  views: ViewName[] = ['Command Center', 'Topics & KPI', 'Pipelines', 'Raw Documents', 'Enriched Intelligence'];
  view: ViewName = 'Command Center';
  now = new Date();
  command: any;
  overview: any = {};
  sources: any[] = [];
  topics: any[] = [];
  kpis: any[] = [];
  latestItems: any[] = [];
  ingestionRuns: any[] = [];
  enrichmentRuns: any[] = [];
  documents: any[] = [];
  enrichedItems: any[] = [];
  topicDetail: any;
  runDetail: any;
  documentDetail: any;
  enrichedDetail: any;
  selectedTopic: any;
  documentSearch = '';
  enrichedSearch = '';
  riskLevel = '';

  constructor(private readonly api: RadarApiService) {}

  ngOnInit(): void {
    this.refresh();
    setInterval(() => (this.now = new Date()), 1000);
  }

  setView(view: ViewName): void {
    this.view = view;
    if (view === 'Raw Documents' && !this.documents.length) this.loadDocuments();
    if (view === 'Enriched Intelligence' && !this.enrichedItems.length) this.loadEnriched();
  }

  refresh(): void {
    this.api.commandCenter().subscribe((data) => {
      this.command = data;
      this.overview = data.overview || {};
      this.sources = data.sources || [];
      this.topics = data.topics || [];
      this.kpis = data.kpis || [];
      this.latestItems = data.latest_items || [];
      this.ingestionRuns = data.ingestion_runs || [];
      this.enrichmentRuns = data.enrichment_runs || [];
      if (!this.topicDetail && this.topics[0]) this.openTopic(this.topics[0]);
    });
  }

  openTopic(topic: any): void {
    this.selectedTopic = topic;
    this.api.topicDetail(topic.id).subscribe((data) => (this.topicDetail = data));
    this.view = 'Topics & KPI';
  }

  selectRun(runId: string): void {
    this.api.runDetail(runId).subscribe((data) => (this.runDetail = data));
  }

  loadDocuments(): void {
    this.api.documents({ search: this.documentSearch }).subscribe((rows) => (this.documents = rows));
  }

  openDocument(document: any): void {
    this.api.documentDetail(document.id).subscribe((data) => (this.documentDetail = data));
  }

  loadEnriched(): void {
    this.api.enrichedItems({ search: this.enrichedSearch, risk_level: this.riskLevel }).subscribe((rows) => (this.enrichedItems = rows));
  }

  openEnriched(item: any): void {
    if (!item?.id) return;
    this.api.enrichedItemDetail(item.id).subscribe((data) => (this.enrichedDetail = data));
    this.view = 'Enriched Intelligence';
  }

  riskClass = riskClass;
  shortId = shortId;
}
