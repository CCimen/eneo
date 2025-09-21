<!--
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
-->

<script lang="ts">
  import { Button, Markdown } from "@intric/ui";
  import { IconCheckCircle } from "@intric/icons/check-circle";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { IconChevronRight } from "@intric/icons/chevron-right";
  import { IconDocument } from "@intric/icons/document";
  import { IconDownload } from "@intric/icons/download";
  import { IconLoadingSpinner } from "@intric/icons/loading-spinner";
  import { getMessageContext } from "$lib/features/chat/MessageContext.svelte";
  import type { ResearchResults } from "$lib/types/research";

  const { current } = getMessageContext();
  const message = $derived(current());

  // Get research results from message
  const results: ResearchResults = $derived(message.research_results);
  const session = $derived(message.research_session);

  let exportingFormat = $state<string | null>(null);
  let showDetails = $state(false);
  let expandedSections = $state<Set<string>>(new Set());

  async function exportReport(format: string) {
    if (!session || exportingFormat) return;
    
    exportingFormat = format;
    console.log('🔍 Exporting research report:', format);

    try {
      const response = await fetch(`/api/research/sessions/${session.id}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format,
          include_citations: true,
          include_metadata: true
        })
      });

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `research_report_${session.id}.${format === 'markdown' ? 'md' : format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      console.log('🔍 Export successful:', format);
    } catch (error) {
      console.error('Export failed:', error);
      // Could add error message to chat
    } finally {
      exportingFormat = null;
    }
  }

  function toggleSection(sectionKey: string) {
    if (expandedSections.has(sectionKey)) {
      expandedSections.delete(sectionKey);
    } else {
      expandedSections.add(sectionKey);
    }
    expandedSections = new Set(expandedSections);
  }
</script>

{#if results}
  <div class="border-default bg-primary rounded-2xl border shadow-sm">
    <!-- Header -->
    <div class="border-default border-b p-6">
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="bg-positive-dimmer text-positive-stronger flex h-10 w-10 items-center justify-center rounded-full">
            <IconCheckCircle class="h-5 w-5" />
          </div>
          <div>
            <h3 class="text-primary text-lg font-semibold">Research Complete</h3>
            <p class="text-secondary text-sm">
              Found {results.total_sources || 0} sources
            </p>
          </div>
        </div>
        
        <!-- Export Buttons -->
        <div class="flex items-center gap-2">
          <Button
            variant="simple"
            padding="text"
            onclick={() => showDetails = !showDetails}
          >
            {#if showDetails}
              <IconChevronDown class="h-4 w-4" />
              Hide Details
            {:else}
              <IconChevronRight class="h-4 w-4" />
              Show Details
            {/if}
          </Button>
        </div>
      </div>
    </div>

    <!-- Executive Summary -->
    <div class="p-6">
      <div class="mb-6">
        <h4 class="text-primary font-semibold mb-3">Executive Summary</h4>
        <div class="bg-secondary rounded-lg p-4">
          <Markdown source={results.executive_summary || 'No summary available'} />
        </div>
      </div>

      <!-- Show Details Section -->
      {#if showDetails && results.report_content}
        <div class="space-y-4">
          <h4 class="text-primary font-semibold">Detailed Research Findings</h4>
          
          <!-- Research Sections -->
          {#if results.report_content.sections}
            <div class="space-y-3">
              {#each results.report_content.sections as section}
                <div class="border-default border rounded-lg overflow-hidden">
                  <button
                    onclick={() => toggleSection(section.title)}
                    class="hover:bg-hover-dimmer flex w-full items-center justify-between p-4 transition-colors"
                  >
                    <h5 class="text-primary font-medium">{section.title}</h5>
                    {#if expandedSections.has(section.title)}
                      <IconChevronDown class="h-5 w-5 text-secondary" />
                    {:else}
                      <IconChevronRight class="h-5 w-5 text-secondary" />
                    {/if}
                  </button>
                  
                  {#if expandedSections.has(section.title)}
                    <div class="border-default border-t p-4">
                      <Markdown source={section.content} />
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}

          <!-- Sources -->
          {#if results.report_content.sources && results.report_content.sources.length > 0}
            <div class="mt-6">
              <h4 class="text-primary font-semibold mb-3">Sources</h4>
              <div class="bg-secondary rounded-lg p-4">
                <ul class="space-y-2">
                  {#each results.report_content.sources as source, i}
                    <li class="flex items-start gap-2">
                      <span class="text-accent-default font-mono text-sm">[{i + 1}]</span>
                      <span class="text-primary text-sm">{source}</span>
                    </li>
                  {/each}
                </ul>
              </div>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Confidence Score -->
      {#if results.confidence_score !== undefined}
        <div class="mt-4">
          <div class="flex items-center justify-between text-sm">
            <span class="text-secondary">Confidence Score</span>
            <span class="text-primary font-medium">
              {Math.round(results.confidence_score * 100)}%
            </span>
          </div>
          <div class="bg-tertiary h-2 w-full overflow-hidden rounded-full mt-1">
            <div 
              class="bg-accent-default h-full transition-all"
              style="width: {results.confidence_score * 100}%"
            ></div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Export Actions -->
    <div class="border-default bg-tertiary border-t p-4">
      <div class="flex items-center justify-between">
        <p class="text-secondary text-sm">Export your research report</p>
        <div class="flex items-center gap-2">
          {#each [
            { key: 'pdf', label: 'PDF' },
            { key: 'markdown', label: 'Markdown' },
            { key: 'txt', label: 'Text' }
          ] as format}
            <Button
              variant="outlined"
              padding="text"
              disabled={exportingFormat !== null}
              onclick={() => exportReport(format.key)}
            >
              {#if exportingFormat === format.key}
                <IconLoadingSpinner class="h-4 w-4 animate-spin" />
              {:else}
                <IconDownload class="h-4 w-4" />
              {/if}
              {format.label}
            </Button>
          {/each}
        </div>
      </div>
    </div>
  </div>
{/if}