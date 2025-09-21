/*
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
*/

import type { 
	ResearchSession, 
	ResearchPlan, 
	ResearchConfiguration,
	ResearchResults
} from '$lib/types/research';

class ResearchAPI {
	private baseUrl = '/api/research';

	async createSession(data: {
		query: string;
		mode: string;
		assistant_id: string;
		space_id?: string;
	}): Promise<ResearchSession> {
		console.log('API: Creating research session', { query: data.query.slice(0, 50), mode: data.mode });
		
		try {
			const response = await fetch(`${this.baseUrl}/sessions`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(data)
			});

			console.log('API: Create session response', { status: response.status, ok: response.ok });

			if (!response.ok) {
				const errorText = await response.text();
				console.error('API: Create session failed', { status: response.status, error: errorText });
				
				let errorMessage = `Failed to create research session (${response.status})`;
				try {
					const errorData = JSON.parse(errorText);
					if (errorData.detail) {
						errorMessage = errorData.detail;
					}
				} catch {
					// Use response text if not JSON
					if (errorText) {
						errorMessage = errorText;
					}
				}
				
				throw new Error(errorMessage);
			}

			const result = await response.json();
			console.log('API: Session created successfully', { sessionId: result.id });
			return result;
			
		} catch (error) {
			console.error('API: Create session error', error);
			throw error;
		}
	}

	async getSession(sessionId: string): Promise<ResearchSession> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}`);
		
		if (!response.ok) {
			throw new Error('Failed to get research session');
		}

		return response.json();
	}

	async listSessions(params?: {
		page?: number;
		limit?: number;
		status?: string;
		space_id?: string;
	}): Promise<{ sessions: ResearchSession[]; pagination: any }> {
		const searchParams = new URLSearchParams();
		
		if (params?.page) searchParams.set('page', params.page.toString());
		if (params?.limit) searchParams.set('limit', params.limit.toString());
		if (params?.status) searchParams.set('status_filter', params.status);
		if (params?.space_id) searchParams.set('space_id', params.space_id);

		const response = await fetch(`${this.baseUrl}/sessions?${searchParams}`);
		
		if (!response.ok) {
			throw new Error('Failed to list research sessions');
		}

		return response.json();
	}

	async getResearchPlan(sessionId: string): Promise<ResearchPlan> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}/plan`);
		
		if (!response.ok) {
			throw new Error('Failed to get research plan');
		}

		return response.json();
	}

	async approvePlan(sessionId: string, data: { approved: boolean }): Promise<void> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}/approve`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(data)
		});

		if (!response.ok) {
			throw new Error('Failed to approve research plan');
		}
	}

	async getResults(sessionId: string): Promise<ResearchResults> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}/results`);
		
		if (!response.ok) {
			throw new Error('Failed to get research results');
		}

		return response.json();
	}

	async exportReport(sessionId: string, format: string): Promise<Blob> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}/export`, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({
				format,
				include_citations: true,
				include_metadata: true
			})
		});

		if (!response.ok) {
			throw new Error('Failed to export research report');
		}

		return response.blob();
	}

	async getConfiguration(assistantId: string): Promise<ResearchConfiguration> {
		const response = await fetch(`${this.baseUrl}/configurations/${assistantId}`);
		
		if (!response.ok) {
			throw new Error('Failed to get research configuration');
		}

		return response.json();
	}

	async updateConfiguration(
		assistantId: string, 
		config: Partial<Omit<ResearchConfiguration, 'id' | 'assistant_id' | 'created_at' | 'updated_at'>>
	): Promise<ResearchConfiguration> {
		const response = await fetch(`${this.baseUrl}/configurations/${assistantId}`, {
			method: 'PUT',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify(config)
		});

		if (!response.ok) {
			throw new Error('Failed to update research configuration');
		}

		return response.json();
	}

	async cancelSession(sessionId: string): Promise<void> {
		const response = await fetch(`${this.baseUrl}/sessions/${sessionId}`, {
			method: 'DELETE'
		});

		if (!response.ok) {
			throw new Error('Failed to cancel research session');
		}
	}
}

export const researchApi = new ResearchAPI();