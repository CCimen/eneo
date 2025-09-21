<script lang="ts">
  import AttachmentUploadIconButton from "$lib/features/attachments/components/AttachmentUploadIconButton.svelte";
  import { IconEnter } from "@intric/icons/enter";
  import { IconStopCircle } from "@intric/icons/stop-circle";
  import { IconFileImage } from "@intric/icons/file-image";
  import { Button, Input, Dropdown, Tooltip } from "@intric/ui";
  import { IconCheck } from "@intric/icons/check";
  import { getAttachmentManager } from "$lib/features/attachments/AttachmentManager";
  import MentionInput from "../mentions/MentionInput.svelte";
  import { initMentionInput } from "../mentions/MentionInput";
  import MentionButton from "../mentions/MentionButton.svelte";
  import { getChatService } from "../../ChatService.svelte";
  import { IconWeb } from "@intric/icons/web";
  import { track } from "$lib/core/helpers/track";
  import { getAppContext } from "$lib/core/AppContext";

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

  function queueUploadsFromClipboard(event: ClipboardEvent) {
    if (!event.clipboardData) return;
    if (!event.clipboardData.files) return;
    if (!(event.clipboardData.files.length > 0)) return;

    queueValidUploads([...event.clipboardData.files]);
  }

  function ask() {
    if (isAskingDisabled) return;
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

    if (isImageMode) {
      console.log('[Chat Input] Image generation enabled', {
        size: imageSize,
        question: $question.substring(0, 100) + '...'
      });
    }

    chat.askQuestion(
      $question,
      files,
      tools,
      webSearchEnabled,
      abortController,
      {
        imageGeneration: isImageMode,
        imageSize: isImageMode ? imageSize : undefined
      }
    ).catch(error => {
      console.error('[Chat Input] Failed to send message:', error);
    });

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
  let isImageMode = $state(false);
  let imageSize = $state<string>("1024x1024");

  const imageSizeOptions = [
    { value: "1024x1024", label: "Square", shortLabel: "1:1", description: "1024×1024" },
    { value: "1024x1792", label: "Portrait", shortLabel: "9:16", description: "1024×1792" },
    { value: "1792x1024", label: "Landscape", shortLabel: "16:9", description: "1792×1024" }
  ];

  const currentSizeOption = $derived(
    imageSizeOptions.find(opt => opt.value === imageSize) || imageSizeOptions[0]
  );

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
  onsubmit={(e) => {
    // Prevent default form submission - we handle submission via the Send button click
    e.preventDefault();
    ask();
  }}
  class="border-default bg-primary ring-dimmer focus-within:border-stronger hover:border-stronger flex w-[100%] max-w-[74ch] flex-col gap-2 border-t p-1.5 shadow-md ring-offset-0 transition-colors duration-300 focus-within:shadow-lg hover:ring-4 md:w-full md:rounded-xl md:border"
>
  <MentionInput onpaste={queueUploadsFromClipboard}></MentionInput>

  <div class="flex justify-between">
    <div class="flex items-center gap-2">
      <AttachmentUploadIconButton label="Upload documents to your conversation" />
      {#if shouldShowMentionButton}
        <MentionButton></MentionButton>
      {/if}
      <Dropdown.Root>
        <Dropdown.Trigger let:trigger asFragment>
          <Button
            unstyled
            type="button"
            aria-label={isImageMode ? "Configure image generation" : "Enable image generation"}
            is={trigger}
            on:click={() => {
              if (!isImageMode) {
                isImageMode = true;
              }
            }}
            class="{isImageMode ? 'bg-accent-dimmer text-accent-stronger border-accent-default' : 'hover:bg-accent-dimmer hover:text-accent-stronger border-default hover:border-accent-default'} flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 text-sm transition-colors"
            title={isImageMode ? `Image mode: ${currentSizeOption.description}` : "Enable image generation"}
          >
            <IconFileImage class="h-4 w-4" />
            <span>Image</span>
            {#if isImageMode}
              <span class="text-xs font-semibold bg-accent-default text-on-fill px-1.5 py-0.5 rounded-full">
                {currentSizeOption.shortLabel}
              </span>
            {/if}
          </Button>
        </Dropdown.Trigger>
        <Dropdown.Menu let:item>
          <div class="p-1.5">
            <div class="text-xs text-secondary font-semibold uppercase tracking-wider px-2 py-1.5 mb-0.5">Select Size</div>
            {#each imageSizeOptions as option}
              <Button
                is={item}
                unstyled
                on:click={() => {
                  imageSize = option.value;
                  isImageMode = true;
                }}
                class="flex items-center justify-between w-full px-2 py-2 rounded-md hover:bg-hover-dimmer text-sm transition-all {imageSize === option.value ? 'bg-accent-dimmer text-accent-stronger font-medium' : ''} group"
              >
                <span class="flex flex-col items-start gap-0.5">
                  <span class="flex items-center gap-2">
                    {option.label}
                    <span class="text-xs text-secondary {imageSize === option.value ? 'text-accent-default' : ''}">{option.shortLabel}</span>
                  </span>
                  <span class="text-xs text-secondary">{option.description}</span>
                </span>
                {#if imageSize === option.value}
                  <IconCheck class="h-4 w-4 text-accent-stronger flex-shrink-0" />
                {/if}
              </Button>
            {/each}
            {#if isImageMode}
              <div class="border-t border-default mt-2 pt-2">
                <Button
                  is={item}
                  unstyled
                  on:click={() => {
                    isImageMode = false;
                  }}
                  class="flex items-center w-full px-2 py-1.5 rounded-md hover:bg-hover-dimmer text-sm text-secondary transition-all"
                >
                  <span>Turn off image generation</span>
                </Button>
              </div>
            {/if}
          </div>
        </Dropdown.Menu>
      </Dropdown.Root>
      {#if chat.partner.type === "default-assistant" && featureFlags.showWebSearch}
        <div
          class="hover:bg-accent-dimmer hover:text-accent-stronger border-default hover:border-accent-default flex items-center justify-center rounded-full border p-1.5"
        >
          <Input.Switch bind:value={useWebSearch} class="*:!cursor-pointer">
            <span class="-mr-2 flex gap-1"><IconWeb></IconWeb>Search</span></Input.Switch
          >
        </div>
      {/if}
    </div>

    {#if chat.askQuestion.isLoading}
      <Tooltip text="Cancel your request" placement="top" let:trigger asFragment>
        <Button
          unstyled
          aria-label="Cancel your request"
          type="submit"
          is={trigger}
          on:click={() => abortController?.abort("User cancelled")}
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
        on:click={() => ask()}
        name="ask"
        class="bg-secondary hover:bg-hover-stronger disabled:bg-tertiary disabled:text-secondary flex h-9 items-center justify-center !gap-1 rounded-lg !pr-1 !pl-2"
      >
        Send
        <IconEnter />
      </Button>
    {/if}
  </div>
</form>
