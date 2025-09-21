<!--
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
-->

<script lang="ts">
	import { createEventDispatcher, onMount, onDestroy } from 'svelte';
	import { ProgressBar } from '@intric/ui';
	import type { ProgressUpdate } from '$lib/types/research';

	export let sessionId: string;

	const dispatch = createEventDispatcher<{
		complete: { sessionId: string; results: any };
		error: string;
	}>();

	let progress = 0;
	let status = 'searching';
	let currentStep = 'Starting research...';
	let sourcesFound = 0;
	let branchesComplete = 0;
	let totalBranches = 0;
	let websocket: WebSocket | null = null;
	let reconnectAttempts = 0;
	let maxReconnectAttempts = 5;

	onMount(() => {
		connectWebSocket();
	});

	onDestroy(() => {
		if (websocket) {
			websocket.close();
		}
	});

	function connectWebSocket() {
		try {
			// Get WebSocket URL (replace http with ws)
			const wsUrl = window.location.origin.replace('http', 'ws') + `/ws/research/${sessionId}/progress`;
			console.log(`Frontend: Connecting to research progress WebSocket: ${wsUrl}`);
			
			websocket = new WebSocket(wsUrl);

			websocket.onopen = () => {
				console.log('Frontend: Research progress WebSocket connected successfully');
				reconnectAttempts = 0;
			};

			websocket.onmessage = (event) => {
				try {
					console.log('Frontend: WebSocket message received', event.data);
					const message = JSON.parse(event.data);
					
					if (message.type === 'deep_research_update' && message.data) {
						console.log('Frontend: Processing progress update', message.data);
						handleProgressUpdate(message.data);
					} else {
						console.log('Frontend: Ignoring non-research WebSocket message', message.type);
					}
				} catch (err) {
					console.error('Frontend: Failed to parse WebSocket message', err, event.data);
				}
			};

			websocket.onclose = (event) => {
				console.log(`Frontend: Research progress WebSocket closed: code=${event.code}, reason=${event.reason}`);
				
				// Only reconnect if not manually closed and research is still active
				if (event.code !== 1000 && status !== 'complete' && status !== 'failed') {
					console.log('Frontend: WebSocket closed unexpectedly, attempting reconnect');
					tryReconnect();
				}
			};

			websocket.onerror = (error) => {
				console.error('Frontend: Research progress WebSocket error', error);
			};

		} catch (err) {
			console.error('Frontend: Failed to connect to research progress WebSocket', err);
			dispatch('error', `Failed to connect to progress updates: ${err instanceof Error ? err.message : 'Unknown error'}`);
		}
	}

	function tryReconnect() {
		if (reconnectAttempts < maxReconnectAttempts) {
			reconnectAttempts++;
			console.log(`Attempting to reconnect WebSocket (${reconnectAttempts}/${maxReconnectAttempts})`);
			
			setTimeout(() => {
				connectWebSocket();
			}, Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)); // Exponential backoff, max 30s
		} else {
			dispatch('error', 'Lost connection to research progress updates');
		}
	}

	function handleProgressUpdate(update: ProgressUpdate) {
		progress = update.progress;
		status = update.status;
		currentStep = update.current_step;
		sourcesFound = update.sources_found;
		branchesComplete = update.branches_complete;
		totalBranches = update.total_branches;

		// If research is complete, dispatch completion event
		if (status === 'complete') {
			dispatch('complete', { sessionId, results: update });
			
			// Close WebSocket connection
			if (websocket) {
				websocket.close();
			}
		}

		// If research failed, dispatch error
		if (status === 'failed') {
			dispatch('error', currentStep || 'Research failed');
			
			// Close WebSocket connection
			if (websocket) {
				websocket.close();
			}
		}
	}

	function getStatusColor(status: string): string {
		switch (status) {
			case 'searching':
				return 'bg-blue-500';
			case 'synthesizing':
				return 'bg-purple-500';
			case 'complete':
				return 'bg-green-500';
			case 'failed':
				return 'bg-red-500';
			default:
				return 'bg-gray-500';
		}
	}

	function getStatusLabel(status: string): string {
		switch (status) {
			case 'searching':
				return 'Researching';
			case 'synthesizing':
				return 'Synthesizing';
			case 'complete':
				return 'Complete';
			case 'failed':
				return 'Failed';
			default:
				return 'Processing';
		}
	}
</script>

<div class="research-progress space-y-6">
	<!-- Progress Bar -->
	<div>
		<div class="flex justify-between items-center mb-2">
			<span class="text-sm font-medium text-gray-700">
				Research Progress
			</span>
			<span class="text-sm text-gray-600">
				{progress}%
			</span>
		</div>
		<ProgressBar value={progress} max={100} class="w-full" />
	</div>

	<!-- Status and Current Step -->
	<div class="flex items-center space-x-3">
		<div class="flex items-center space-x-2">
			<div class={`w-3 h-3 rounded-full ${getStatusColor(status)}`}></div>
			<span class="text-sm font-medium text-gray-700">
				{getStatusLabel(status)}
			</span>
		</div>
		{#if status === 'searching' || status === 'synthesizing'}
			<div class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
		{/if}
	</div>

	<div class="bg-gray-50 rounded-lg p-4">
		<p class="text-sm text-gray-800 mb-3">
			{currentStep}
		</p>

		<!-- Research Metrics -->
		{#if totalBranches > 0}
			<div class="grid grid-cols-2 gap-4 text-sm">
				<div>
					<span class="text-gray-600">Sources Found:</span>
					<span class="font-medium ml-2">{sourcesFound}</span>
				</div>
				<div>
					<span class="text-gray-600">Branches:</span>
					<span class="font-medium ml-2">{branchesComplete}/{totalBranches}</span>
				</div>
			</div>
		{/if}

		<!-- Branch Progress Visualization -->
		{#if totalBranches > 0 && branchesComplete > 0}
			<div class="mt-3">
				<div class="text-xs text-gray-500 mb-1">Research Branches</div>
				<div class="flex space-x-1">
					{#each Array(totalBranches) as _, index}
						<div class={`h-2 flex-1 rounded ${
							index < branchesComplete 
								? 'bg-green-400' 
								: index === branchesComplete && status === 'searching'
									? 'bg-blue-400 animate-pulse'
									: 'bg-gray-200'
						}`}></div>
					{/each}
				</div>
			</div>
		{/if}
	</div>

	<!-- Estimated Time Remaining -->
	{#if status === 'searching' && progress > 0 && progress < 100}
		<div class="text-xs text-gray-500 text-center">
			Research in progress... This may take a few minutes.
		</div>
	{/if}
</div>

<style>
	.research-progress {
		min-height: 200px;
	}
</style>