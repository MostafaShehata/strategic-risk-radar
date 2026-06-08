import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommandCenterApi } from './api.service';
import { EventCardComponent } from './components/event-card.component';
import { MetricCardComponent } from './components/metric-card.component';
import { StatusPillComponent } from './components/status-pill.component';
import { asList, riskClass, shortId } from './ui';

type ViewName = 'Command Center' | 'Trending Events' | '360 Impact' | 'Briefing Report' | 'Impact Simulator' | 'Use Cases';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, MetricCardComponent, EventCardComponent, StatusPillComponent],
  template: `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="crest">ICP</span>
          <div>
            <strong>Command Center</strong>
            <small>Executive intelligence</small>
          </div>
        </div>
        <button *ngFor="let item of views" [class.active]="view === item" (click)="setView(item)">{{ item }}</button>
        <div class="system-card">
          <small>Selected topic</small>
          <strong>{{ selectedEvent?.title || 'No selection' }}</strong>
          <span>{{ selectedEvent?.risk_level || 'select an event' }}</span>
        </div>
      </aside>

      <main>
        <header class="hero">
          <div>
            <span class="eyebrow">UAE ICP STRATEGIC RADAR</span>
            <h1>Decision Intelligence Command Center</h1>
            <p>Executive view for global events, UAE impact, KPI exposure, RAG evidence, and scenario assessment.</p>
          </div>
          <button (click)="refresh()">Refresh</button>
        </header>

        <section class="metric-grid">
          <cc-metric-card label="Active topics" [value]="overview.active_topics || 0" hint="LLM strategic events"></cc-metric-card>
          <cc-metric-card label="High risk" [value]="overview.high_risk_topics || 0" hint="high or critical topics"></cc-metric-card>
          <cc-metric-card label="KPI impacts" [value]="overview.kpi_impacts || 0" hint="ICP impact rows"></cc-metric-card>
          <cc-metric-card label="Enriched news" [value]="overview.enriched_documents || 0" hint="agent processed"></cc-metric-card>
          <cc-metric-card label="Running jobs" [value]="(overview.ingestion_running || 0) + (overview.enrichment_running || 0)" hint="live pipelines"></cc-metric-card>
        </section>

        <section *ngIf="view === 'Command Center'" class="dashboard-grid">
          <section class="world-panel">
            <div class="map-glow"></div>
            <div class="map-copy">
              <span class="eyebrow">GLOBAL MONITORING ACTIVE</span>
              <h2>{{ topEvents[0]?.title || 'Waiting for strategic topics' }}</h2>
              <p>{{ topEvents[0]?.uae_impact || topEvents[0]?.summary || 'Ingest and enrich news to populate executive impact.' }}</p>
              <button *ngIf="topEvents[0]" (click)="openEvent(topEvents[0])">Open 360 View</button>
            </div>
          </section>
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">TOP UAE-RELEVANT EVENTS</span><h2>Priority board</h2></div>
            <cc-event-card *ngFor="let event of topEvents" [event]="event" (open)="openEvent($event)"></cc-event-card>
          </section>
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">KPI EXPOSURE</span><h2>Operational impact</h2></div>
            <article class="kpi-row" *ngFor="let kpi of dashboard?.kpis">
              <div><strong>{{ kpi.kpi_name }}</strong><small>{{ kpi.article_count }} articles</small></div>
              <b>{{ kpi.highest_risk_score }}</b>
            </article>
          </section>
          <section class="panel wide">
            <div class="panel-title"><span class="eyebrow">ACTIVITY FEED</span><h2>Latest intelligence</h2></div>
            <button class="activity-row" *ngFor="let item of dashboard?.activity" (click)="openEvent({id: item.topic_id, title: item.topic_title})">
              <cc-status-pill [label]="item.risk_level"></cc-status-pill>
              <span>{{ item.title }}</span>
              <small>{{ item.source_id }} / {{ item.created_at | date:'medium' }}</small>
            </button>
          </section>
        </section>

        <section *ngIf="view === 'Trending Events'" class="events-page">
          <div class="filters">
            <input [(ngModel)]="search" placeholder="Search events" (keyup.enter)="loadEvents()" />
            <select [(ngModel)]="riskFilter" (change)="loadEvents()">
              <option value="">All risk</option><option>critical</option><option>high</option><option>medium</option><option>low</option>
            </select>
            <button (click)="loadEvents()">Apply</button>
          </div>
          <div class="event-grid">
            <cc-event-card *ngFor="let event of events" [event]="event" (open)="openEvent($event)"></cc-event-card>
          </div>
        </section>

        <section *ngIf="view === '360 Impact'" class="impact-layout">
          <section class="panel focus-panel">
            <ng-container *ngIf="detail?.topic; else noEvent">
              <div class="impact-score" [class]="riskClass(detail.topic.risk_level)">
                <span>UAE relevance</span><strong>{{ detail.topic.risk_score }}/100</strong><cc-status-pill [label]="detail.topic.risk_level"></cc-status-pill>
              </div>
              <h2>{{ detail.topic.title }}</h2>
              <p class="lead">{{ detail.topic.uae_impact || detail.topic.summary }}</p>
              <div class="dependency-map">
                <div class="node event-node">{{ detail.topic.title }}</div>
                <div class="node" *ngFor="let kpi of detail.kpis.slice(0,4)">{{ kpi.kpi_name }}<b>{{ kpi.highest_risk_score }}</b></div>
              </div>
            </ng-container>
            <ng-template #noEvent><p class="empty">Select an event from Trending Events to open the 360 impact view.</p></ng-template>
          </section>
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">KPI IMPACT</span><h2>Business effect</h2></div>
            <article class="kpi-detail" *ngFor="let kpi of detail?.kpis">
              <strong>{{ kpi.kpi_name }}</strong><span>{{ kpi.highest_risk_score }}</span><p>{{ kpi.impact_summary }}</p>
            </article>
          </section>
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">RAG CHAT</span><h2>Ask this topic</h2></div>
            <textarea [(ngModel)]="chatQuestion" placeholder="Ask about the current situation and impact on ICP"></textarea>
            <button [disabled]="!detail?.topic" (click)="askTopic()">Ask RAG</button>
            <p class="lead" *ngIf="chatAnswer">{{ chatAnswer }}</p>
            <article class="evidence" *ngFor="let hit of chatEvidence"><small>Score {{ hit.score }}</small><p>{{ hit.text }}</p></article>
          </section>
          <section class="panel wide">
            <div class="panel-title"><span class="eyebrow">RELATED NEWS</span><h2>Evidence articles</h2></div>
            <table><tr><th>Article</th><th>Source</th><th>Risk</th></tr><tr *ngFor="let article of detail?.articles"><td>{{ article.title }}</td><td>{{ article.source_id }}</td><td>{{ article.risk_score }} {{ article.risk_level }}</td></tr></table>
          </section>
        </section>

        <section *ngIf="view === 'Briefing Report'" class="panel report">
          <div class="panel-title"><span class="eyebrow">EXECUTIVE BRIEF</span><h2>{{ briefing?.title }}</h2></div>
          <article class="brief-item" *ngFor="let rec of briefing?.recommendations">
            <cc-status-pill [label]="rec.priority"></cc-status-pill>
            <div><h3>{{ rec.title }}</h3><p>{{ rec.rationale }}</p><div class="chips"><span *ngFor="let k of asList(rec.affected_kpis)">{{ k }}</span></div></div>
          </article>
        </section>

        <section *ngIf="view === 'Impact Simulator'" class="simulator-grid">
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">WHAT-IF</span><h2>Scenario simulator</h2></div>
            <select [(ngModel)]="simulationTopicId"><option value="">No specific topic</option><option *ngFor="let event of events" [value]="event.id">{{ event.title }}</option></select>
            <textarea [(ngModel)]="scenario" placeholder="What if Hormuz disruption continues for 30 days?"></textarea>
            <label>Severity {{ severity }}<input type="range" min="1" max="100" [(ngModel)]="severity"></label>
            <label>Duration {{ durationDays }} days<input type="range" min="1" max="90" [(ngModel)]="durationDays"></label>
            <button (click)="runSimulation()">Run simulation</button>
          </section>
          <section class="panel" *ngIf="simulation">
            <div class="impact-score" [class]="riskClass(simulation.projected_level)">
              <span>Projected risk</span><strong>{{ simulation.projected_score }}/100</strong><cc-status-pill [label]="simulation.projected_level"></cc-status-pill>
            </div>
            <h3>Decision matrix</h3>
            <article class="decision" *ngFor="let row of simulation.decision_matrix"><strong>{{ row.option }}</strong><p>{{ row.benefit }} / {{ row.risk }}</p><small>Confidence {{ row.confidence }}</small></article>
          </section>
        </section>

        <section *ngIf="view === 'Use Cases'" class="usecase-grid">
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">IMPLEMENTED</span><h2>Works with current repo data</h2></div>
            <article *ngFor="let uc of useCases?.implemented"><strong>{{ uc.name }}</strong><p>{{ uc.basis }}</p></article>
          </section>
          <section class="panel">
            <div class="panel-title"><span class="eyebrow">NEEDS ICP DATA</span><h2>Not fully possible yet</h2></div>
            <article *ngFor="let uc of useCases?.needs_internal_data"><strong>{{ uc.name }}</strong><p>{{ uc.basis }}</p></article>
          </section>
        </section>
      </main>
    </div>
  `,
})
export class AppComponent implements OnInit {
  views: ViewName[] = ['Command Center', 'Trending Events', '360 Impact', 'Briefing Report', 'Impact Simulator', 'Use Cases'];
  view: ViewName = 'Command Center';
  dashboard: any;
  overview: any = {};
  topEvents: any[] = [];
  events: any[] = [];
  detail: any;
  selectedEvent: any;
  briefing: any;
  useCases: any;
  search = '';
  riskFilter = '';
  scenario = 'What if the selected disruption continues for 30 days?';
  severity = 75;
  durationDays = 30;
  simulationTopicId = '';
  simulation: any;
  chatQuestion = 'What is the latest impact on UAE operations?';
  chatAnswer = '';
  chatEvidence: any[] = [];

  constructor(private readonly api: CommandCenterApi) {}

  ngOnInit(): void {
    this.refresh();
  }

  setView(view: ViewName): void {
    this.view = view;
    if (view === 'Trending Events') this.loadEvents();
    if (view === 'Briefing Report') this.loadBriefing();
    if (view === 'Use Cases') this.loadUseCases();
  }

  refresh(): void {
    this.api.dashboard().subscribe((data) => {
      this.dashboard = data;
      this.overview = data.overview || {};
      this.topEvents = data.top_events || [];
      if (!this.events.length) this.events = this.topEvents;
      if (!this.selectedEvent && this.topEvents[0]) this.openEvent(this.topEvents[0], false);
    });
  }

  loadEvents(): void {
    this.api.events({ risk_level: this.riskFilter, search: this.search }).subscribe((data) => (this.events = data));
  }

  openEvent(event: any, navigate = true): void {
    if (!event?.id) return;
    this.selectedEvent = event;
    this.simulationTopicId = event.id;
    this.api.eventDetail(event.id).subscribe((data) => (this.detail = data));
    if (navigate) this.view = '360 Impact';
  }

  loadBriefing(): void {
    this.api.briefing().subscribe((data) => (this.briefing = data));
  }

  loadUseCases(): void {
    this.api.useCases().subscribe((data) => (this.useCases = data));
  }

  runSimulation(): void {
    this.api.simulate({
      topic_id: this.simulationTopicId || undefined,
      scenario: this.scenario,
      severity: Number(this.severity),
      duration_days: Number(this.durationDays),
    }).subscribe((data) => (this.simulation = data));
  }

  askTopic(): void {
    const topicId = this.detail?.topic?.id;
    if (!topicId) return;
    this.api.topicChat({ topic_id: topicId, question: this.chatQuestion, top_k: 5 }).subscribe((data) => {
      this.chatAnswer = data.answer;
      this.chatEvidence = data.evidence || [];
    });
  }

  asList = asList;
  riskClass = riskClass;
  shortId = shortId;
}
