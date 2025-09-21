<script lang="ts">
  import AttachmentUploadIconButton from "$lib/features/attachments/components/AttachmentUploadIconButton.svelte";
  import { IconEnter } from "@intric/icons/enter";
  import { IconStopCircle } from "@intric/icons/stop-circle";
  import { Button, Input, Tooltip } from "@intric/ui";
  import { getAttachmentManager } from "$lib/features/attachments/AttachmentManager";
  import MentionInput from "../mentions/MentionInput.svelte";
  import { initMentionInput } from "../mentions/MentionInput";
  import MentionButton from "../mentions/MentionButton.svelte";
  import { getChatService } from "../../ChatService.svelte";
  import { IconWeb } from "@intric/icons/web";
  import { IconDocument } from "@intric/icons/document";
  import { IconLoadingSpinner } from "@intric/icons/loading-spinner";
  import { IconSearch } from "@intric/icons/search";
  import { IconCheckCircle } from "@intric/icons/check-circle";
  import { track } from "$lib/core/helpers/track";
  import { getAppContext } from "$lib/core/AppContext";
  import ResearchModal from "$lib/components/research/ResearchModal.svelte";
  import { writable } from "svelte/store";

  const chat = getChatService();
  const { featureFlags } = getAppContext();

  const {
    state: { attachments, isUploading },
    queueValidUploads,
    clearUploads
  } = getAttachmentManager();

  const {
    states: { mentions, question },
    resetMentionInput,
    focusMentionInput
  } = initMentionInput({
    triggerCharacter: "@",
    tools: () => chat.partner.tools,
    onEnterPressed: ask
  });

  type Props = { scrollToBottom: () => void };

  const { scrollToBottom }: Props = $props();

  let abortController: AbortController | undefined;
  const researchModalOpen = writable(false);

  function toggleResearchMode() {
    console.log('🔍 Research button clicked!');
    
    if (chat.researchMode.active) {
      // Deactivate research mode
      chat.deactivateResearchMode();
      console.log('🔍 Research mode deactivated');
    } else {
      // Show research mode selection
      chat.activateResearchMode();
      console.log('🔍 Research mode activated');
    }
  }

  function queueUploadsFromClipboard(event: ClipboardEvent) {
    if (!event.clipboardData) return;
    if (!event.clipboardData.files) return;
    if (!(event.clipboardData.files.length > 0)) return;

    queueValidUploads([...event.clipboardData.files]);
  }

  function ask() {
    if (isAskingDisabled) return;
    
    // Handle research mode
    if (chat.researchMode.active && chat.researchMode.selectedMode) {
      console.log('🔍 Starting research with query:', $question);
      chat.startResearch($question, chat.researchMode.selectedMode);
      scrollToBottom();
      resetMentionInput();
      clearUploads();
      return;
    }
    
    // Normal chat flow
    const webSearchEnabled = featureFlags.showWebSearch && useWebSearch;
    const files = $attachments.map((file) => file?.fileRef).filter((file) => file !== undefined);
    abortController = new AbortController();
    const tools =
      $mentions.length > 0
        ? {
            assistants: $mentions.map((mention) => {
              return { id: mention.id, handle: mention.handle };
            })
          }
        : undefined;
    chat.askQuestion($question, files, tools, webSearchEnabled, abortController);
    scrollToBottom();
    resetMentionInput();
    clearUploads();
  }

  $effect(() => {
    track(chat.partner, chat.currentConversation);
    focusMentionInput();
  });

  const isAskingDisabled = $derived(
    chat.askQuestion.isLoading || $isUploading || ($question === "" && $attachments.length === 0)
  );

  let useWebSearch = $state(false);

  const shouldShowMentionButton = $derived.by(() => {
    const hasTools = chat.partner.tools.assistants.length > 0;
    const isEnabled =
      chat.partner.type === "default-assistant" ||
      ("allow_mentions" in chat.partner && chat.partner.allow_mentions);
    return hasTools && isEnabled;
  });
</script>

<!-- This interaction is just a convenience function -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<form
  onclick={() => {
    focusMentionInput();
  }}
  class="border-default bg-primary ring-dimmer focus-within:border-stronger hover:border-stronger flex w-[100%] max-w-[74ch] flex-col gap-2 border-t p-1.5 shadow-md ring-offset-0 transition-colors duration-300 focus-within:shadow-lg hover:ring-4 md:w-full md:rounded-xl md:border"
>
  <!-- Research Mode Selection (appears when research mode is active) -->
  {#if chat.researchMode.active}
    <div class="bg-secondary border-default border rounded-xl p-4 transition-all duration-200">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="bg-accent-dimmer p-2 rounded-lg">
            <IconDocument class="text-accent-strong h-5 w-5" />
          </div>
          <div>
            <h3 class="text-primary font-semibold text-sm">Deep Research Mode</h3>
            <p class="text-secondary text-xs">AI-powered comprehensive analysis</p>
          </div>
        </div>
        <Button
          variant="simple"
          padding="icon"
          onclick={() => chat.deactivateResearchMode()}
          class="text-secondary hover:text-primary hover:bg-hover-dimmer rounded-lg transition-colors"
        >
          <IconStopCircle class="h-4 w-4" />
        </Button>
      </div>

      {#if !chat.researchMode.selectedMode}
        <p class="text-primary font-medium text-sm mb-3">Choose your research depth:</p>
        <div class="grid grid-cols-3 gap-2">
          {#each [
            {
              key: 'quick',
              label: 'Quick',
              desc: '30-60s',
              icon: 'lightning',
              details: 'Fast overview',
              color: 'blue'
            },
            {
              key: 'standard',
              label: 'Standard',
              desc: '2-3min',
              icon: 'search',
              details: 'Balanced depth',
              color: 'purple'
            },
            {
              key: 'deep',
              label: 'Deep',
              desc: '3-5min',
              icon: 'layers',
              details: 'Comprehensive',
              color: 'green'
            }
          ] as mode}
            <button
              onclick={() => chat.activateResearchMode(mode.key)}
              class="group relative overflow-hidden rounded-lg border transition-all duration-200 hover:shadow-md active:scale-[0.98] {
                chat.researchMode.selectedMode === mode.key
                  ? 'border-accent-strong bg-accent-dimmer shadow-sm'
                  : 'border-default bg-secondary hover:bg-hover-dimmer hover:border-stronger'
              }"
            >
              <!-- Gradient overlay for selected state -->
              {#if chat.researchMode.selectedMode === mode.key}
                <div class="absolute inset-0 bg-gradient-to-br from-accent-default/10 to-transparent pointer-events-none"></div>
              {/if}

              <div class="relative p-3 flex flex-col items-center gap-2">
                <!-- Icon with proper contrast -->
                <div class="{
                  chat.researchMode.selectedMode === mode.key
                    ? 'bg-accent-strong/20 text-accent-stronger'
                    : 'bg-tertiary text-secondary group-hover:bg-hover-stronger group-hover:text-primary'
                } p-2 rounded-lg transition-colors">
                  {#if mode.key === 'quick'}
                    <IconLoadingSpinner class="h-5 w-5" />
                  {:else if mode.key === 'standard'}
                    <IconSearch class="h-5 w-5" />
                  {:else}
                    <IconDocument class="h-5 w-5" />
                  {/if}
                </div>

                <!-- Mode name with high contrast -->
                <div class="text-center">
                  <p class="font-semibold text-sm {
                    chat.researchMode.selectedMode === mode.key
                      ? 'text-accent-stronger'
                      : 'text-primary'
                  }">{mode.label}</p>
                  <p class="text-xs mt-0.5 {
                    chat.researchMode.selectedMode === mode.key
                      ? 'text-accent-strong'
                      : 'text-secondary'
                  }">{mode.details}</p>
                </div>

                <!-- Time badge with better visibility -->
                <div class="{
                  chat.researchMode.selectedMode === mode.key
                    ? 'bg-accent-strong/20 text-accent-stronger border-accent-strong/30 scale-105'
                    : 'bg-tertiary text-secondary border-default group-hover:scale-105'
                } px-2 py-0.5 rounded-full text-xs font-medium border transition-transform duration-200">
                  <span>{mode.desc}</span>
                </div>

                <!-- Selection indicator -->
                {#if chat.researchMode.selectedMode === mode.key}
                  <div class="absolute top-2 right-2">
                    <IconCheckCircle class="h-4 w-4 text-accent-stronger" />
                  </div>
                {/if}
              </div>
            </button>
          {/each}
        </div>
      {:else}
        <!-- Selected mode display with enhanced visibility -->
        <div class="bg-accent-dimmer/20 rounded-lg p-3 border border-accent-default/20">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <!-- Mode indicator badge -->
              <div class="relative">
                <div class="bg-accent-strong/20 backdrop-blur-sm px-3 py-1.5 rounded-full border border-accent-strong/30 flex items-center gap-2 shadow-sm">
                  {#if chat.researchMode.selectedMode === 'quick'}
                    <IconLoadingSpinner class="h-3.5 w-3.5 text-accent-stronger" />
                  {:else if chat.researchMode.selectedMode === 'standard'}
                    <IconSearch class="h-3.5 w-3.5 text-accent-stronger" />
                  {:else}
                    <IconDocument class="h-3.5 w-3.5 text-accent-stronger" />
                  {/if}
                  <span class="text-accent-stronger text-xs font-bold tracking-wider">
                    {chat.researchMode.selectedMode?.toUpperCase()} MODE
                  </span>
                </div>
              </div>

              <!-- Time estimate -->
              <div class="flex items-center gap-1.5 text-sm">
                <span class="text-secondary">Est. time:</span>
                <span class="text-primary font-semibold">
                  {chat.researchMode.selectedMode === 'quick' ? '30-60s' :
                   chat.researchMode.selectedMode === 'standard' ? '2-3min' : '3-5min'}
                </span>
              </div>
            </div>

            <!-- Change mode button with better visibility -->
            <Button
              variant="outlined"
              padding="text"
              onclick={() => chat.activateResearchMode()}
              class="text-primary border-stronger hover:bg-hover-dimmer hover:border-accent-default transition-all"
            >
              <IconDocument class="h-3.5 w-3.5" />
              Change Mode
            </Button>
          </div>

          <!-- Clear instruction with visual emphasis -->
          <div class="mt-3 bg-secondary rounded-lg p-3 border border-default">
            <div class="flex items-start gap-3">
              <div class="bg-accent-default/10 p-1.5 rounded-lg">
                <IconWeb class="h-4 w-4 text-accent-default" />
              </div>
              <div class="flex-1">
                <p class="text-primary text-sm font-medium mb-1">
                  Ready to research
                </p>
                <p class="text-secondary text-xs leading-relaxed">
                  Type your research question below and press <kbd class="bg-accent-dimmer text-accent-stronger px-2 py-0.5 rounded text-xs font-semibold border border-accent-default/30">Enter</kbd> to start your {chat.researchMode.selectedMode} analysis
                </p>
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  {/if}

  <MentionInput onpaste={queueUploadsFromClipboard}></MentionInput>

  <div class="flex justify-between">
    <div class="flex items-center gap-2">
      <AttachmentUploadIconButton label="Upload documents to your conversation" />
      {#if shouldShowMentionButton}
        <MentionButton></MentionButton>
      {/if}
      {#if chat.partner.type === "default-assistant" && featureFlags.showWebSearch}
        <div
          class="hover:bg-accent-dimmer hover:text-accent-stronger border-default hover:border-accent-default flex items-center justify-center rounded-full border p-1.5"
        >
          <Input.Switch bind:value={useWebSearch} class="*:!cursor-pointer">
            <span class="-mr-2 flex gap-1"><IconWeb></IconWeb>Search</span></Input.Switch
          >
        </div>
      {/if}
      
      <!-- Deep Research Button -->
      <Tooltip text={chat.researchMode.active ? "Research mode active - click to deactivate" : "Start deep research on any topic"} placement="top" let:trigger asFragment>
        <Button
          unstyled
          aria-label="Deep Research"
          is={trigger}
          onclick={toggleResearchMode}
          class="{chat.researchMode.active
            ? 'bg-accent-dimmer text-accent-stronger border border-accent-strong hover:bg-accent-default/30'
            : 'bg-secondary text-primary border border-default hover:bg-hover-dimmer hover:border-accent-default hover:text-accent-default'} flex h-9 items-center justify-center gap-1.5 rounded-lg px-3 transition-all duration-200 font-medium"
        >
          {#if chat.researchMode.active}
            <span class="relative inline-flex rounded-full h-2 w-2 bg-accent-stronger"></span>
          {:else}
            <IconDocument class="text-current h-4 w-4" />
          {/if}
          <span class="text-sm">Research</span>
        </Button>
      </Tooltip>
    </div>

    {#if chat.askQuestion.isLoading}
      <Tooltip text="Cancel your request" placement="top" let:trigger asFragment>
        <Button
          unstyled
          aria-label="Cancel your request"
          type="submit"
          is={trigger}
          onclick={() => abortController?.abort("User cancelled")}
          name="ask"
          class="bg-secondary hover:bg-hover-stronger disabled:bg-tertiary disabled:text-secondary flex h-9 items-center justify-center !gap-1 rounded-lg !pr-1 !pl-2"
        >
          Stop answer
          <IconStopCircle />
        </Button>
      </Tooltip>
    {:else}
      <Button
        disabled={isAskingDisabled}
        aria-label="Submit your question"
        type="submit"
        onclick={() => ask()}
        name="ask"
        class="bg-secondary hover:bg-hover-stronger disabled:bg-tertiary disabled:text-secondary flex h-9 items-center justify-center !gap-1 rounded-lg !pr-1 !pl-2"
      >
        Send
        <IconEnter />
      </Button>
    {/if}
  </div>
</form>

<!-- Research Modal -->
<ResearchModal 
  openController={researchModalOpen}
  assistant={{ id: chat.partner.id, name: chat.partner.name }}
  spaceId={chat.partner.space_id || null}
  on:sessionCreated={(e) => {
    // Could add chat message about research starting
    console.log('Research session created:', e.detail.session.id);
  }}
  on:researchComplete={(e) => {
    // Could add research results to chat
    console.log('Research completed:', e.detail);
  }}
/>
