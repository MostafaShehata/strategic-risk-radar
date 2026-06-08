import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class RadarApiService {
  constructor(private readonly http: HttpClient) {}

  commandCenter() {
    return this.http.get<any>('/api/command-center');
  }

  overview() {
    return this.http.get<any>('/api/overview');
  }

  ingestionSummary() {
    return this.http.get<any[]>('/api/summary/ingestion');
  }

  enrichmentSummary() {
    return this.http.get<any[]>('/api/summary/enrichment');
  }

  ragStatus() {
    return this.http.get<any>('/api/rag/status');
  }

  runs(sourceType = '', status = '') {
    return this.http.get<any[]>('/api/runs', { params: { source_type: sourceType, status } });
  }

  runDetail(runId: string) {
    return this.http.get<any>(`/api/runs/${runId}`);
  }

  enrichmentRuns(status = '') {
    return this.http.get<any[]>('/api/enrichment/runs', { params: { status } });
  }

  enrichmentRunDetail(runId: string) {
    return this.http.get<any>(`/api/enrichment/runs/${runId}`);
  }

  topics() {
    return this.http.get<any[]>('/api/enrichment/topics');
  }

  topicDetail(topicId: string) {
    return this.http.get<any>(`/api/enrichment/topics/${topicId}`);
  }

  kpis() {
    return this.http.get<any[]>('/api/enrichment/kpis');
  }

  documents(filters: { search?: string; source?: string; keyword?: string } = {}) {
    let params = new HttpParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params = params.set(key, value);
    });
    return this.http.get<any[]>('/api/documents', { params });
  }

  documentDetail(id: string) {
    return this.http.get<any>(`/api/documents/${id}`);
  }

  enrichedItems(filters: { search?: string; source?: string; risk_level?: string; keyword?: string; min_score?: number } = {}) {
    let params = new HttpParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    });
    return this.http.get<any[]>('/api/enrichment/items', { params });
  }

  enrichedItemDetail(id: string) {
    return this.http.get<any>(`/api/enrichment/items/${id}`);
  }

  filterOptions() {
    return this.http.get<any>('/api/enrichment/filter-options');
  }

  sourceTypes() {
    return this.http.get<any[]>('/api/source-types');
  }

  documentKeywords() {
    return this.http.get<any[]>('/api/document-keywords');
  }
}
