<!--
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
-->

<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { writable } from 'svelte/store';
	import { Button, Dialog, Input } from '@intric/ui';
	import type { ResearchSession, ResearchPlan, ResearchMode } from '$lib/types/research';
	import { researchApi } from '$lib/api/research';
	import ResearchProgressTracker from './ResearchProgressTracker.svelte';

	// Assistant interface (simplified for this component)
	interface Assistant {
		id: string;
		name: string;
	}

	export let assistant: Assistant;
	export let spaceId: string | null = null;

	const dispatch = createEventDispatcher<{
		sessionCreated: { session: ResearchSession };
		researchComplete: { session: ResearchSession; results: any };
	}>();

	// Dialog state
	const isOpen = writable(false);

	// Research state
	let query = '';
	let mode: ResearchMode = 'standard';
	let currentSession: ResearchSession | null = null;
	let currentPlan: ResearchPlan | null = null;
	let isLoading = false;
	let error: string | null = null;
	let debugInfo: string[] = [];
	let step: 'input' | 'plan-approval' | 'execution' | 'results' = 'input';

	// Mode configurations
	const modeConfigs = {
		quick: {
			label: 'Quick Research',
			description: '30-60 seconds • Basic overview with key findings',
			duration: '30-60s'
		},
		standard: {
			label: 'Standard Research', 
			description: '2-3 minutes • Comprehensive analysis with multiple sources',
			duration: '2-3min'
		},
		deep: {
			label: 'Deep Research',
			description: '3-5 minutes • Extensive multi-level research with detailed analysis',
			duration: '3-5min'
		}
	};

	// Public method to open modal
	export function open() {
		isOpen.set(true);
	}

	async function handleStartResearch() {
		console.log('Frontend: Starting research session', { query: query.slice(0, 50), mode, assistantId: assistant.id, spaceId });
		
		if (!query.trim()) {
			error = 'Please enter a research query';
			console.warn('Frontend: Empty query provided');
			return;
		}

		if (query.length > 1000) {
			error = 'Research query too long (max 1000 characters)';
			console.warn('Frontend: Query too long', { length: query.length });
			return;
		}

		isLoading = true;
		error = null;
		debugInfo = [];

		try {
			console.log('Frontend: Calling createSession API');
			debugInfo.push(`${new Date().toISOString()}: Creating session with mode ${mode}`);
			
			const session = await researchApi.createSession({
				query: query.trim(),
				mode,
				assistant_id: assistant.id,
				space_id: spaceId
			});

			console.log('Frontend: Session created successfully', { sessionId: session.id, status: session.status });
			debugInfo.push(`${new Date().toISOString()}: Session created: ${session.id}`);

			currentSession = session;
			step = 'plan-approval';
			dispatch('sessionCreated', { session });

			// Poll for plan generation
			debugInfo.push(`${new Date().toISOString()}: Starting plan polling`);
			await pollForPlan(session.id);
		} catch (err) {
			console.error('Frontend: Failed to start research', err);
			
			if (err instanceof Error) {
				// Try to extract specific error info
				if (err.message.includes('400')) {
					error = 'Invalid request. Please check your input and try again.';
				} else if (err.message.includes('401') || err.message.includes('403')) {
					error = 'Permission denied. Please check your access rights.';
				} else if (err.message.includes('500')) {
					error = 'Server error. Please try again or contact support.';
				} else {
					error = err.message;
				}
				
				debugInfo.push(`${new Date().toISOString()}: Error - ${err.message}`);
			} else {
				error = 'Failed to start research';
				debugInfo.push(`${new Date().toISOString()}: Unknown error`);
			}
		} finally {
			isLoading = false;
		}
	}

	async function pollForPlan(sessionId: string) {
		console.log('Frontend: Starting plan polling for session', sessionId);
		const maxAttempts = 30; // 30 seconds
		let attempts = 0;

		const poll = async () => {
			try {
				attempts++;
				console.log(`Frontend: Polling for plan (attempt ${attempts}/${maxAttempts})`);
				debugInfo.push(`${new Date().toISOString()}: Polling attempt ${attempts}`);
				
				const plan = await researchApi.getResearchPlan(sessionId);
				console.log('Frontend: Plan retrieved successfully', { planId: plan.id, branches: plan.questions.levels.length });
				debugInfo.push(`${new Date().toISOString()}: Plan retrieved successfully`);
				currentPlan = plan;
				return;
			} catch (err) {
				console.log(`Frontend: Plan not ready yet (attempt ${attempts}/${maxAttempts})`, err);
				
				if (attempts < maxAttempts) {
					setTimeout(poll, 1000);
				} else {
					console.error('Frontend: Plan polling timeout after 30 seconds');
					error = 'Failed to generate research plan - timeout after 30 seconds';
					debugInfo.push(`${new Date().toISOString()}: Plan polling timeout`);
				}
			}
		};

		await poll();
	}

	async function handleApprovePlan(approved: boolean) {
		if (!currentSession) return;

		isLoading = true;
		error = null;

		try {
			await researchApi.approvePlan(currentSession.id, { approved });
			
			if (approved) {
				step = 'execution';
			} else {
				// Reset to input for new query
				step = 'input';
				currentSession = null;
				currentPlan = null;
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to approve plan';
		} finally {
			isLoading = false;
		}
	}

	function handleResearchComplete(event: CustomEvent) {
		step = 'results';
		dispatch('researchComplete', event.detail);
	}

	function handleClose() {
		// Reset state
		query = '';
		mode = 'standard';
		currentSession = null;
		currentPlan = null;
		step = 'input';
		error = null;
		isOpen.set(false);
	}

	function formatEstimatedTime(seconds: number): string {
		if (seconds < 60) return `${seconds}s`;
		const minutes = Math.round(seconds / 60);
		return `${minutes}min`;
	}
</script>

<Dialog.Root bind:isOpen on:close={handleClose}>
	<Dialog.Content class="max-w-2xl">
		<Dialog.Title>Deep Research</Dialog.Title>
		<Dialog.Description>
			Conduct comprehensive, multi-level research on any topic using AI.
		</Dialog.Description>

		<div class="mt-6 space-y-6">
			{#if error}
				<div class="bg-red-50 border border-red-200 rounded-md p-3">
					<p class="text-sm text-red-800 font-medium">{error}</p>
					{#if debugInfo.length > 0}
						<details class="mt-2">
							<summary class="text-xs text-red-600 cursor-pointer">Debug Information</summary>
							<div class="mt-2 text-xs text-red-600 font-mono space-y-1">
								{#each debugInfo as info}
									<div>{info}</div>
								{/each}
							</div>
						</details>
					{/if}
				</div>
			{/if}

			{#if step === 'input'}
				<!-- Research Query Input -->
				<div class="space-y-4">
					<div>
						<label for="query" class="block text-sm font-medium text-gray-700 mb-2">
							Research Query
						</label>
						<Input.Root>
							<Input.Input
								id="query"
								bind:value={query}
								placeholder="e.g., Impact of AI adoption on municipal services"
								disabled={isLoading}
							/>
						</Input.Root>
						<p class="text-sm text-gray-500 mt-1">
							Describe what you want to research in natural language
						</p>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-3">
							Research Depth
						</label>
						<div class="space-y-3">
							{#each Object.entries(modeConfigs) as [modeKey, config]}
								<label class="flex items-start space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer">
									<input
										type="radio"
										name="mode"
										value={modeKey}
										bind:group={mode}
										class="mt-1"
									/>
									<div class="flex-1">
										<div class="flex items-center justify-between">
											<span class="font-medium text-gray-900">{config.label}</span>
											<span class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
												{config.duration}
											</span>
										</div>
										<p class="text-sm text-gray-600 mt-1">{config.description}</p>
									</div>
								</label>
							{/each}
						</div>
					</div>
				</div>

			{:else if step === 'plan-approval'}
				<!-- Research Plan Approval -->
				<div class="space-y-4">
					<div>
						<h3 class="text-lg font-medium text-gray-900 mb-2">Research Plan</h3>
						<p class="text-sm text-gray-600">
							Review the generated research plan before execution begins.
						</p>
					</div>

					{#if currentPlan}
						<div class="border rounded-lg p-4 bg-gray-50">
							<div class="flex justify-between items-start mb-4">
								<div>
									<h4 class="font-medium text-gray-900">{currentPlan.questions.main_topic}</h4>
									<p class="text-sm text-gray-600 mt-1">
										{currentPlan.estimated_sources} sources • {formatEstimatedTime(currentPlan.estimated_duration)}
									</p>
								</div>
								<span class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
									{modeConfigs[mode].label}
								</span>
							</div>

							<div class="space-y-4">
								{#each currentPlan.questions.levels as level}
									<div>
										<h5 class="text-sm font-medium text-gray-700 mb-2">
											Level {level.level} - {level.level === 1 ? 'Broad Research' : 'Deep Dive'}
										</h5>
										<div class="space-y-2">
											{#each level.branches as branch}
												<div class="bg-white p-3 rounded border">
													<p class="text-sm text-gray-900">{branch.question}</p>
													<p class="text-xs text-gray-600 mt-1">
														{branch.estimated_sources} sources • {branch.type} search
													</p>
												</div>
											{/each}
										</div>
									</div>
								{/each}
							</div>
						</div>
					{:else}
						<div class="text-center py-8">
							<div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
							<p class="text-sm text-gray-600 mt-2">Generating research plan...</p>
						</div>
					{/if}
				</div>

			{:else if step === 'execution'}
				<!-- Research Execution with Progress -->
				<div class="space-y-4">
					<div>
						<h3 class="text-lg font-medium text-gray-900 mb-2">Research in Progress</h3>
						<p class="text-sm text-gray-600">
							Your research is being executed. This may take a few minutes.
						</p>
					</div>

					{#if currentSession}
						<ResearchProgressTracker 
							sessionId={currentSession.id}
							on:complete={handleResearchComplete}
							on:error={(e) => error = e.detail}
						/>
					{/if}
				</div>

			{:else if step === 'results'}
				<!-- Research Results -->
				<div class="space-y-4">
					<div class="text-center py-8">
						<div class="text-green-500 mb-4">
							<svg class="h-16 w-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
							</svg>
						</div>
						<h4 class="text-lg font-medium text-gray-900 mb-2">Research Completed!</h4>
						<p class="text-sm text-gray-600 mb-6">
							Your comprehensive research report is ready for review and export.
						</p>
					</div>
				</div>
			{/if}
		</div>

		<Dialog.Controls>
			{#if step === 'input'}
				<Button variant="secondary" on:click={handleClose}>
					Cancel
				</Button>
				<Button 
					variant="primary" 
					on:click={handleStartResearch}
					disabled={isLoading || !query.trim()}
				>
					{#if isLoading}
						Starting...
					{:else}
						Start Research
					{/if}
				</Button>
			{:else if step === 'plan-approval' && currentPlan}
				<Button 
					variant="secondary" 
					on:click={() => handleApprovePlan(false)}
					disabled={isLoading}
				>
					Reject Plan
				</Button>
				<Button 
					variant="primary" 
					on:click={() => handleApprovePlan(true)}
					disabled={isLoading}
				>
					{#if isLoading}
						Starting...
					{:else}
						Approve & Start Research
					{/if}
				</Button>
			{:else if step === 'results'}
				<Button variant="secondary" on:click={handleClose}>
					Close
				</Button>
				<Button variant="primary" on:click={handleClose}>
					View Results
				</Button>
			{/if}
		</Dialog.Controls>
	</Dialog.Content>
</Dialog.Root>