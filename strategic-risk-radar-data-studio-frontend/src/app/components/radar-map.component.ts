import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { StatusPillComponent } from './status-pill.component';

@Component({
  selector: 'radar-map',
  standalone: true,
  imports: [CommonModule, StatusPillComponent],
  template: `
    <section class="radar-map glass-card">
      <div class="panel-heading">
        <div>
          <span class="eyebrow">GLOBAL WATCH</span>
          <h2>Strategic situation map</h2>
        </div>
        <radar-status-pill [label]="activeTopics ? 'active' : 'quiet'"></radar-status-pill>
      </div>
      <div class="map-canvas">
        <div class="grid-lines"></div>
        <svg viewBox="0 0 800 360" aria-hidden="true">
          <path class="route route-a" d="M120 210 C260 120 420 120 650 185" />
          <path class="route route-b" d="M220 250 C360 310 500 285 705 240" />
          <path class="route route-c" d="M90 150 C220 180 345 220 500 165" />
        </svg>
        <button class="map-pin uae" title="UAE Command Hub"><span>UAE</span></button>
        <button class="map-pin hormuz risk-critical" title="Hormuz / Maritime Watch"><span>Route</span></button>
        <button class="map-pin europe risk-high" title="Europe Mobility Watch"><span>Mobility</span></button>
        <button class="map-pin asia risk-medium" title="Asia Trade Watch"><span>Cargo</span></button>
      </div>
      <div class="map-brief">
        <strong>{{ topTopic?.title || 'No strategic topic selected' }}</strong>
        <p>{{ topTopic?.uae_impact || topTopic?.summary || 'Waiting for enriched intelligence topics from the pipeline.' }}</p>
      </div>
    </section>
  `,
})
export class RadarMapComponent {
  @Input() topTopic: any;
  @Input() activeTopics = 0;
}
