import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class CommandCenterApi {
  constructor(private readonly http: HttpClient) {}

  dashboard() {
    return this.http.get<any>('/api/dashboard');
  }

  useCases() {
    return this.http.get<any>('/api/use-cases');
  }

  events(filters: { risk_level?: string; search?: string } = {}) {
    return this.http.get<any[]>('/api/events', { params: filters });
  }

  eventDetail(id: string) {
    return this.http.get<any>(`/api/events/${id}`);
  }

  briefing() {
    return this.http.get<any>('/api/briefing');
  }

  simulate(payload: { topic_id?: string; scenario: string; severity: number; duration_days: number }) {
    return this.http.post<any>('/api/simulation', payload);
  }

  topicChat(payload: { topic_id: string; question: string; top_k: number }) {
    return this.http.post<any>('/api/topic-chat', payload);
  }
}
