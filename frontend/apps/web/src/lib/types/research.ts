/*
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
*/

export type ResearchMode = 'quick' | 'standard' | 'deep';

export type SessionStatus = 
	| 'planning' 
	| 'pending_approval' 
	| 'running' 
	| 'completed' 
	| 'failed' 
	| 'cancelled';

export interface ResearchSession {
	id: string;
	query: string;
	mode: ResearchMode;
	status: SessionStatus;
	assistant_id: string;
	space_id?: string;
	created_at: string;
	updated_at: string;
	started_at?: string;
	completed_at?: string;
	max_breadth: number;
	max_depth: number;
	timeout_minutes: number;
}

export interface ResearchBranch {
	id: string;
	parent?: string;
	question: string;
	type: 'broad' | 'deep';
	estimated_sources: number;
}

export interface ResearchLevel {
	level: number;
	branches: ResearchBranch[];
}

export interface ResearchQuestions {
	main_topic: string;
	levels: ResearchLevel[];
}

export interface ResearchPlan {
	id: string;
	session_id: string;
	questions: ResearchQuestions;
	estimated_duration: number;
	estimated_sources: number;
	approved: boolean;
	created_at: string;
}

export interface ResearchConfiguration {
	id: string;
	assistant_id: string;
	max_breadth: number;
	max_depth: number;
	quick_timeout_seconds: number;
	standard_timeout_seconds: number;
	deep_timeout_seconds: number;
	sources_per_query: number;
	enable_web_search: boolean;
	enable_academic_sources: boolean;
	created_at: string;
	updated_at: string;
}

export interface ProgressUpdate {
	session_id: string;
	status: string;
	progress: number;
	current_step: string;
	sources_found: number;
	branches_complete: number;
	total_branches: number;
	timestamp: string;
}

export interface Citation {
	id: number;
	title: string;
	url: string;
	author?: string;
	publish_date?: string;
	access_date: string;
	domain: string;
}

export interface ReportSection {
	title: string;
	content: string;
	subsections: {
		title: string;
		content: string;
		citations: number[];
	}[];
	citations: number[];
}

export interface ResearchResults {
	id: string;
	session_id: string;
	executive_summary: string;
	report_content: {
		sections: ReportSection[];
		citations: Citation[];
		metadata: {
			total_words: number;
			research_duration: string;
			sources_by_type: Record<string, number>;
		};
	};
	total_sources: number;
	total_findings: number;
	confidence_score: number;
	limitations?: string;
	created_at: string;
}