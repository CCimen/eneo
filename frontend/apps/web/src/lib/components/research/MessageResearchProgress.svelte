<!--
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
-->

<script lang="ts">
  import { Button, ProgressBar } from "@intric/ui";
  import { IconLoadingSpinner } from "@intric/icons/loading-spinner";
  import { IconSearch } from "@intric/icons/search";
  import { IconDocument } from "@intric/icons/document";
  import { IconClose } from "@intric/icons/close";
  import { IconAlertCircle } from "@intric/icons/alert-circle";
  import { IconClock } from "@intric/icons/clock";
  import { getMessageContext } from "$lib/features/chat/MessageContext.svelte";
  import { getChatService } from "$lib/features/chat/ChatService.svelte";

  const { current } = getMessageContext();
  const message = $derived(current());
  const chat = getChatService();

  // Get progress data from message
  const progress = $derived(message.research_progress || {
    status: 'searching',
    progress: 0,
    current_step: 'Initializing research...',
    sources_found: 0,
    branches_complete: 0,
    total_branches: 0,
    error_message: null
  });

  // Calculate progress percentage (0-100)
  const progressPercentage = $derived(
    Math.min(100, Math.max(0, progress.progress || 0))
  );

  // Time tracking
  let startTime = $state(Date.now());
  let elapsedSeconds = $state(0);

  $effect(() => {
    const interval = setInterval(() => {
      elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    }, 1000);
    return () => clearInterval(interval);
  });

  function formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  // Get status message
  function getStatusLabel(status: string): string {
    switch (status) {
      case 'searching': return 'Researching';
      case 'synthesizing': return 'Synthesizing Results';
      case 'complete': return 'Research Complete';
      case 'failed': return 'Research Failed';
      default: return 'Starting...';
    }
  }

  async function cancelResearch() {
    const session = message.research_session;
    if (!session) return;

    if (confirm('Are you sure you want to cancel this research?')) {
      console.log('🔍 Cancelling research:', session.id);

      try {
        const response = await fetch(`/api/research/sessions/${session.id}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
          chat.deactivateResearchMode();
          message.answer = 'Research cancelled by user.';
          message.research_type = 'research_cancelled';
        }
      } catch (error) {
        console.error('Failed to cancel research:', error);
      }
    }
  }
</script>

<div class="border-default bg-primary rounded-2xl border shadow-sm">
  <!-- Header -->
  <div class="border-default border-b p-6 bg-gradient-to-r from-primary to-secondary/20">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="{progress.status === 'failed' ? 'bg-negative-dimmer' : 'bg-accent-dimmer'} flex h-10 w-10 items-center justify-center rounded-full">
          {#if progress.status === 'failed'}
            <IconAlertCircle class="h-5 w-5 text-negative-stronger" />
          {:else}
            <IconLoadingSpinner class="h-5 w-5 animate-spin text-accent-stronger" />
          {/if}
        </div>
        <div>
          <h3 class="text-primary text-lg font-semibold">Research in Progress</h3>
          <p class="text-secondary text-sm">{getStatusLabel(progress.status)}</p>
        </div>
      </div>
      {#if progress.status === 'searching' || progress.status === 'synthesizing'}
        <Button
          variant="simple"
          padding="text"
          onclick={cancelResearch}
        >
          <IconClose class="h-4 w-4" />
          Cancel
        </Button>
      {/if}
    </div>
  </div>
  
  <!-- Progress Content -->
  <div class="p-6">
    <!-- Progress Bar -->
    <div class="mb-6">
      <div class="mb-2 flex items-center justify-between text-sm">
        <span class="text-secondary">Progress</span>
        <span class="text-primary font-medium">{progressPercentage}%</span>
      </div>
      <div class="relative">
        <ProgressBar progress={progressPercentage} />
        {#if progressPercentage > 0 && progressPercentage < 100}
          <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer" style="animation: shimmer 2s infinite;"></div>
        {/if}
      </div>
    </div>
    
    <!-- Status Details -->
    <div class="bg-gradient-to-br from-secondary/80 to-tertiary/50 rounded-lg p-4 border border-default/30 shadow-sm">
      <div class="space-y-3">
        <!-- Current Step -->
        {#if progress.current_step}
          <div class="flex items-start gap-3">
            <IconSearch class="text-accent-default mt-0.5 h-4 w-4 flex-shrink-0" />
            <div class="flex-1">
              <p class="text-secondary text-xs uppercase tracking-wider">Current Step</p>
              <p class="text-primary text-sm font-medium">{progress.current_step}</p>
            </div>
          </div>
        {/if}

        <!-- Elapsed Time -->
        <div class="flex items-start gap-3">
          <IconClock class="text-accent-default mt-0.5 h-4 w-4 flex-shrink-0" />
          <div class="flex-1">
            <p class="text-secondary text-xs uppercase tracking-wider">Elapsed Time</p>
            <p class="text-primary text-sm font-medium">{formatTime(elapsedSeconds)}</p>
          </div>
        </div>

        <!-- Sources Found -->
        {#if progress.sources_found !== undefined && progress.sources_found > 0}
          <div class="flex items-start gap-3">
            <IconDocument class="text-accent-default mt-0.5 h-4 w-4 flex-shrink-0" />
            <div class="flex-1">
              <p class="text-secondary text-xs uppercase tracking-wider">Sources Found</p>
              <p class="text-primary text-sm font-medium">{progress.sources_found}</p>
            </div>
          </div>
        {/if}

        <!-- Branch Progress -->
        {#if progress.total_branches > 0}
          <div class="flex items-start gap-3">
            <div class="mt-1.5 h-2 w-2 rounded-full bg-accent-default animate-pulse shadow-sm"></div>
            <div class="flex-1">
              <p class="text-secondary text-xs uppercase tracking-wider">Research Branches</p>
              <p class="text-primary text-sm font-medium">{progress.branches_complete} of {progress.total_branches} complete</p>
            </div>
          </div>
        {/if}
      </div>
    </div>
    
    <!-- Branch Progress Visualization -->
    {#if progress.total_branches > 0}
      <div class="mt-4 p-3 bg-secondary/30 rounded-lg">
        <div class="text-secondary text-xs mb-2 font-medium uppercase tracking-wider">Branch Progress</div>
        <div class="flex gap-1.5">
          {#each Array(progress.total_branches) as _, index}
            <div class="h-2.5 flex-1 rounded-full transition-all duration-300 shadow-sm {
              index < progress.branches_complete 
                ? 'bg-positive-default' 
                : index === progress.branches_complete && progress.status === 'searching'
                  ? 'bg-accent-default animate-pulse'
                  : 'bg-tertiary'
            }"></div>
          {/each}
        </div>
      </div>
    {/if}
    
    <!-- Status Messages -->
    {#if progress.status === 'complete'}
      <div class="bg-positive-dimmer border-positive-default border rounded-lg p-3 text-center mt-4">
        <div class="text-positive-stronger font-medium">
          Research completed successfully!
        </div>
      </div>
    {:else if progress.status === 'failed'}
      <div class="bg-negative-dimmer border-negative-default border rounded-lg p-3 mt-4">
        <div class="flex items-start gap-3">
          <IconAlertCircle class="h-5 w-5 text-negative-stronger flex-shrink-0 mt-0.5" />
          <div class="flex-1">
            <div class="text-negative-stronger font-medium mb-1">
              Research failed
            </div>
            {#if progress.error_message}
              <p class="text-negative-default text-sm">{progress.error_message}</p>
            {:else}
              <p class="text-negative-default text-sm">An unexpected error occurred. Please try again.</p>
            {/if}
            <Button
              variant="outlined"
              padding="text"
              class="mt-3"
              onclick={() => window.location.reload()}
            >
              Retry Research
            </Button>
          </div>
        </div>
      </div>
    {:else if progress.status === 'searching'}
      <!-- Loading Animation -->
      <div class="mt-4 flex items-center justify-center p-2">
        <div class="flex items-center gap-2.5">
          <div class="h-2.5 w-2.5 rounded-full bg-accent-default animate-pulse shadow-sm" style="animation-delay: 0ms"></div>
          <div class="h-2.5 w-2.5 rounded-full bg-accent-default animate-pulse shadow-sm" style="animation-delay: 150ms"></div>
          <div class="h-2.5 w-2.5 rounded-full bg-accent-default animate-pulse shadow-sm" style="animation-delay: 300ms"></div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }
  .animate-shimmer {
    animation: shimmer 2s infinite;
  }
</style>