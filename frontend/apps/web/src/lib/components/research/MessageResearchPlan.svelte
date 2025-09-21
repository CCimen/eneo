<!--
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
-->

<script lang="ts">
  import { Button } from "@intric/ui";
  import { IconLoadingSpinner } from "@intric/icons/loading-spinner";
  import { IconSearch } from "@intric/icons/search";
  import { IconDocument } from "@intric/icons/document";
  import { IconCheckCircle } from "@intric/icons/check-circle";
  import { IconClose } from "@intric/icons/close";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { IconChevronRight } from "@intric/icons/chevron-right";
  import { IconEdit } from "@intric/icons/edit";
  import { getChatService } from "$lib/features/chat/ChatService.svelte";
  import { getMessageContext } from "$lib/features/chat/MessageContext.svelte";
  import type { ResearchPlan } from "$lib/types/research";

  const chat = getChatService();
  const { current } = getMessageContext();
  const message = $derived(current());

  // Get research plan from message
  const researchPlan: ResearchPlan = $derived(message.research_plan);
  const session = $derived(message.research_session);

  let isApproving = $state(false);
  // Auto-expand all levels when plan is loaded
  let expandedLevels = $state<Set<number>>(new Set());
  let editMode = $state(false);
  let editedQuery = $state("");

  // Auto-expand all levels when research plan is loaded
  $effect(() => {
    if (researchPlan?.questions?.levels && expandedLevels.size === 0) {
      const allLevels = new Set<number>();
      for (let i = 0; i < researchPlan.questions.levels.length; i++) {
        allLevels.add(i);
      }
      expandedLevels = allLevels;
    }
  });

  function approvePlan() {
    if (!session || isApproving) return;

    isApproving = true;
    console.log('🔍 Approving research plan for session:', session.id);

    // This now immediately updates the UI and runs approval in background
    chat.approveResearchPlan(session.id);

    // The component will unmount as the message type changes immediately
  }

  function rejectPlan() {
    console.log('🔍 Research plan rejected');
    chat.deactivateResearchMode();
    
    // Update message to show rejection
    message.answer = 'Research plan cancelled. You can start a new research by clicking the research button.';
    message.research_type = 'research_rejected';
  }

  function toggleLevel(level: number) {
    if (expandedLevels.has(level)) {
      expandedLevels.delete(level);
    } else {
      expandedLevels.add(level);
    }
    expandedLevels = new Set(expandedLevels);
  }

  function enableEditMode() {
    editMode = true;
    editedQuery = researchPlan.questions?.main_topic || "";
    // Expand all levels to show the questions that will be regenerated
    if (researchPlan?.questions?.levels?.length > 0) {
      const allLevels = new Set<number>();
      for (let i = 0; i < researchPlan.questions.levels.length; i++) {
        allLevels.add(i);
      }
      expandedLevels = allLevels;
    }
  }

  function cancelEdit() {
    editMode = false;
    editedQuery = "";
  }


  async function saveEditedPlan() {
    if (!editedQuery || !session) return;

    // Show loading state
    editMode = false;
    const previousQuery = researchPlan.questions?.main_topic;

    // Optimistically update UI
    if (researchPlan.questions) {
      researchPlan.questions.main_topic = editedQuery;
    }

    try {
      const response = await fetch(`/api/research/sessions/${session.id}/regenerate-plan`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: editedQuery
        })
      });

      if (response.ok) {
        const newPlan = await response.json();
        // Update the entire plan with new questions/branches
        Object.assign(researchPlan, newPlan);
        console.log('✅ Research plan regenerated with new query');
      } else {
        // Revert on error
        if (researchPlan.questions) {
          researchPlan.questions.main_topic = previousQuery;
        }
        console.error('❌ Failed to regenerate research plan');
        editMode = true; // Re-enable edit mode
      }
    } catch (error) {
      // Revert on error
      if (researchPlan.questions) {
        researchPlan.questions.main_topic = previousQuery;
      }
      console.error('❌ Error regenerating plan:', error);
      editMode = true; // Re-enable edit mode
    }

    editedQuery = "";
  }
</script>

{#if researchPlan}
  <div class="border-default bg-primary rounded-2xl border shadow-sm relative z-0">
    <!-- Header -->
    <div class="border-default border-b p-6">
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <div class="flex items-center gap-3">
            <div class="bg-accent-dimmer text-accent-stronger flex h-10 w-10 items-center justify-center rounded-full">
              <IconSearch class="h-5 w-5" />
            </div>
            <div>
              <h3 class="text-primary text-lg font-semibold">Research Plan</h3>
              <p class="text-secondary text-sm">Review the research strategy</p>
            </div>
          </div>
        </div>
        {#if !editMode && !isApproving}
          <Button
            variant="simple"
            padding="text"
            onclick={enableEditMode}
          >
            <IconEdit class="h-4 w-4" />
            Edit Plan
          </Button>
        {/if}
      </div>

      <!-- Plan Summary -->
      <div class="bg-gradient-to-br from-secondary/80 to-tertiary/50 mt-4 rounded-lg p-4 border border-default/30">
        <p class="text-primary font-medium mb-3">{researchPlan.questions?.main_topic || 'Generating research plan...'}</p>
        <div class="flex items-center gap-6 text-sm">
          <div class="flex items-center gap-2">
            <IconDocument class="h-4 w-4 text-accent-default" />
            <span class="text-secondary">Sources:</span>
            <span class="text-primary font-medium">{researchPlan.estimated_sources || 0}</span>
          </div>
          <div class="flex items-center gap-2">
            <IconLoadingSpinner class="h-4 w-4 text-accent-default" />
            <span class="text-secondary">Duration:</span>
            <span class="text-primary font-medium">{Math.round((researchPlan.estimated_duration || 0) / 60)} min</span>
          </div>
          <div class="flex items-center gap-2">
            <IconSearch class="h-4 w-4 text-accent-default" />
            <span class="text-secondary">Depth:</span>
            <span class="text-primary font-medium">{researchPlan.questions?.levels?.length || 0} levels</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Research Questions Tree -->
    <div class="p-6 max-h-[50vh] overflow-y-auto overflow-x-hidden relative isolate">
      {#if editMode}
        <div class="bg-gradient-to-r from-accent-dimmer/30 to-accent-default/10 border-accent-default/50 rounded-lg border p-4 mb-4 shadow-sm">
          <label class="block text-sm font-medium text-primary mb-2">
            Edit Research Query
          </label>
          <input
            bind:value={editedQuery}
            type="text"
            class="w-full border-stronger bg-primary text-primary ring-default placeholder:text-muted h-10 rounded-lg border px-3 py-2 text-sm shadow focus-within:ring-2 hover:ring-2 focus-visible:ring-2"
            placeholder="Enter your research question..."
            autofocus
            onkeydown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                saveEditedPlan();
              }
              if (e.key === 'Escape') {
                e.preventDefault();
                cancelEdit();
              }
            }}
          />
          <p class="mt-2 text-xs text-secondary">
            Updating the query will regenerate the research plan with new questions
          </p>
        </div>
      {/if}
      <div class="relative">
        <!-- Vertical timeline line -->
        <div class="border-default absolute top-0 bottom-0 left-5 z-0 border-l"></div>
        
        <!-- Research Levels -->
        {#if researchPlan.questions?.levels && researchPlan.questions.levels.length > 0}
          <div class="space-y-4">
            {#each researchPlan.questions.levels as level, levelIndex}
              <div class="relative">
                <!-- Level Node -->
                <div class="relative z-10">
                  <button
                    onclick={() => toggleLevel(levelIndex)}
                    class="hover:bg-hover-dimmer group flex w-full items-center gap-3 rounded-lg p-3 transition-all duration-200 hover:shadow-sm"
                  >
                    <!-- Node Circle -->
                    <div class="border-stronger bg-primary relative flex h-10 w-10 items-center justify-center rounded-full border-2 shadow-sm">
                      <span class="text-primary font-bold text-sm">{levelIndex + 1}</span>
                    </div>
                    
                    <!-- Level Title -->
                    <div class="flex-1 text-left">
                      <div class="flex items-center gap-2">
                        <h4 class="text-primary font-medium">
                          {levelIndex === 0 ? 'Broad Research' : 'Deep Analysis'}
                        </h4>
                        <span class="bg-accent-dimmer/50 text-accent-stronger rounded-full px-2.5 py-1 text-xs font-medium">
                          {level.branches?.length || 0} questions
                        </span>
                      </div>
                      <p class="text-secondary text-sm">
                        {levelIndex === 0 ? 'Initial exploration of the topic' : 'Focused investigation'}
                      </p>
                    </div>
                    
                    <!-- Chevron -->
                    <div class="text-secondary">
                      {#if expandedLevels.has(levelIndex)}
                        <IconChevronDown class="h-5 w-5" />
                      {:else}
                        <IconChevronRight class="h-5 w-5" />
                      {/if}
                    </div>
                  </button>
                  
                  <!-- Questions List -->
                  {#if expandedLevels.has(levelIndex) && level.branches}
                    <div class="ml-14 mt-2 space-y-2">
                      {#each level.branches || [] as branch, branchIndex}
                        <div class="border-default bg-secondary flex items-start gap-3 rounded-lg border p-3 transition-all duration-200 hover:bg-tertiary/50">
                          <IconSearch class="text-accent-default mt-0.5 h-4 w-4 flex-shrink-0" />
                          <p class="text-primary text-sm flex-1">{branch.question}</p>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="border-default bg-tertiary flex items-center justify-between border-t rounded-b-2xl px-6 py-4">
      {#if editMode}
        <Button
          variant="simple"
          onclick={cancelEdit}
        >
          <IconClose class="h-4 w-4" />
          Cancel Edit
        </Button>

        <Button
          variant="primary"
          onclick={saveEditedPlan}
        >
          <IconCheckCircle class="h-4 w-4" />
          Save Changes
        </Button>
      {:else}
        <Button
          variant="simple"
          onclick={rejectPlan}
          disabled={isApproving}
        >
          <IconClose class="h-4 w-4" />
          Cancel Plan
        </Button>

        <Button
          variant="primary"
          onclick={approvePlan}
          disabled={isApproving}
        >
          {#if isApproving}
            <IconLoadingSpinner class="h-4 w-4 animate-spin" />
            Approving...
          {:else}
            <IconCheckCircle class="h-4 w-4" />
            Approve & Start Research
          {/if}
        </Button>
      {/if}
    </div>
  </div>
{/if}