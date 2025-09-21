<script lang="ts">
  import type { ConversationMessage } from "@intric/intric-js";
  import { IconLoadingSpinner } from "@intric/icons/loading-spinner";
  import MessageQuestion from "./MessageQuestion.svelte";
  import MessageAnswer from "./MessageAnswer.svelte";
  import MessageFiles from "./MessageFiles.svelte";
  import MessageTools from "./MessageTools.svelte";
  import MessageResearchPlan from "$lib/components/research/MessageResearchPlan.svelte";
  import MessageResearchProgress from "$lib/components/research/MessageResearchProgress.svelte";
  import MessageResearchResults from "$lib/components/research/MessageResearchResults.svelte";
  import { browser } from "$app/environment";
  import { getChatService } from "../../ChatService.svelte";
  import { setMessageContext } from "../../MessageContext.svelte";
  import { dynamicColour } from "$lib/core/colours";

  interface Props {
    message: ConversationMessage;
    isLast: boolean;
    isLoading: boolean;
  }

  let { message, isLast, isLoading }: Props = $props();

  setMessageContext({
    current: () => message,
    isLast: () => isLast,
    isLoading: () => isLoading
  });

  const chat = getChatService();

  let messageHeight: number = $state(0);

  const updateHeight = (isLast: boolean) => {
    if (!isLast || !browser) {
      messageHeight = 0;
      return;
    }

    setTimeout(() => {
      const viewContainer = document.getElementById("session-view-container");
      const inputContainer = document.getElementById("session-input-container");
      const messageContainer = document.getElementById("session-message-container");
      const question = [...document.querySelectorAll(".question")].pop();

      if (viewContainer && inputContainer && messageContainer && question) {
        const containerHeight = viewContainer.clientHeight;
        const inputFieldHeight = inputContainer.clientHeight;
        const parentPadding = parseInt(getComputedStyle(messageContainer).paddingBottom);
        // If the questoin is longer than 0.5 of the screen, we jump directly to the answer
        const extraSpace =
          question.clientHeight > containerHeight * 0.5 ? question.clientHeight + parentPadding : 0;

        messageHeight = containerHeight - inputFieldHeight - 2 * parentPadding + extraSpace;
      }
    }, 1);
  };

  $effect(() => {
    updateHeight(isLast);
  });

  const showSpinner = $derived.by(() => {
    const isGeneratingImage = message.generated_files.length > 0;
    return isLast && isLoading && !isGeneratingImage;
  });

  const isReasoning = $derived.by(() => {
    const modelCanReason =
      "completion_model" in chat.partner && chat.partner.completion_model?.reasoning;
    const noAnswerReceived = message.answer.trim() === "";
    return modelCanReason && noAnswerReceived;
  });
</script>

<svelte:window onresize={() => updateHeight(isLast)} />

<div
  class="group/message mx-auto flex w-full max-w-[71ch] flex-col gap-4"
  data-is-last-message={isLast}
  style="min-height: {messageHeight}px"
>
  <MessageFiles></MessageFiles>
  <MessageQuestion></MessageQuestion>
  
  <!-- Research Message Components -->
  {#if message.research_type === 'research_plan_generating'}
    <!-- Plan generation loading state -->
    <div 
      {...dynamicColour({ basedOn: 'research-loading' })}
      class="bg-dynamic-dimmer border-dynamic-default my-4 rounded-2xl border"
    >
      <div class="p-4">
        <div class="flex items-center gap-3">
          <IconLoadingSpinner class="h-5 w-5 animate-spin text-accent-default" />
          <div>
            <div class="text-primary font-medium">🔍 Generating research plan</div>
            <div class="text-secondary text-sm">Creating structured research questions...</div>
          </div>
        </div>
      </div>
    </div>
  {:else if message.research_type === 'research_plan'}
    <MessageResearchPlan></MessageResearchPlan>
  {:else if message.research_type === 'research_progress'}
    <MessageResearchProgress></MessageResearchProgress>
  {:else if message.research_type === 'research_results'}
    <MessageResearchResults></MessageResearchResults>
  {:else}
    <MessageAnswer></MessageAnswer>
  {/if}
  
  {#if showSpinner}
    <div class="flex items-center gap-2">
      <IconLoadingSpinner class="animate-spin" />
      {#if isReasoning}
        <span
          class="bg-accent-dimmer text-accent-stronger w-fit animate-pulse rounded-full px-4 py-2"
          >Thinking...</span
        >
      {/if}
    </div>
  {:else}
    <MessageTools></MessageTools>
  {/if}
</div>
