<script lang="ts">
  import { createSelect } from "@melt-ui/svelte";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { IconCheck } from "@intric/icons/check";
  import { IconQuestionMark } from "@intric/icons/question-mark";
  import { Tooltip } from "@intric/ui";
  import { createEventDispatcher } from "svelte";
  
  const dispatch = createEventDispatcher();
  
  // Props are now read-only - we emit events to request changes
  export let kwArgs: {
    temperature?: number | null;
    top_p?: number | null;
    reasoning_effort?: string;
    verbosity?: string;
    reasoning_summary?: string;
    [key: string]: any;
  } = {};
  export let isDisabled: boolean = false;
  
  // Derive current values from kwArgs with defaults
  $: reasoningEffort = kwArgs?.reasoning_effort ?? "medium";
  $: verbosity = kwArgs?.verbosity ?? "medium";
  $: reasoningSummary = kwArgs?.reasoning_summary ?? "disabled";
  
  // Squelch flag prevents programmatic $selected updates from firing writebacks
  let squelchReasoningEffort = false;
  let squelchVerbosity = false;
  let squelchSummary = false;
  
  function squelchOneTick(setter: (val: boolean) => void) { 
    setter(true); 
    queueMicrotask(() => setter(false)); 
  }
  
  const reasoningEffortOptions = [
    { value: "minimal", label: "Minimal", description: "Fastest response, minimal reasoning" },
    { value: "low", label: "Low", description: "Quick responses with basic reasoning" },
    { value: "medium", label: "Medium", description: "Balanced reasoning and response time" },
    { value: "high", label: "High", description: "Thorough reasoning, slower responses" }
  ];
  
  const verbosityOptions = [
    { value: "low", label: "Low", description: "Concise, brief responses" },
    { value: "medium", label: "Medium", description: "Balanced detail level" },
    { value: "high", label: "High", description: "Detailed, comprehensive responses" }
  ];
  
  // Note: Currently only "disabled" and "detailed" are supported by GPT-5 models
  // Auto and Concise are disabled until Azure adds support
  const reasoningSummaryOptions = [
    { value: "disabled", label: "Disabled", description: "No reasoning summary provided", disabled: false },
    { value: "auto", label: "Auto (Not Available)", description: "Not yet supported by current GPT-5 models", disabled: true },
    { value: "concise", label: "Concise (Not Available)", description: "Not yet supported by current GPT-5 models", disabled: true },
    { value: "detailed", label: "Detailed", description: "Comprehensive reasoning explanation", disabled: false }
  ];
  
  // Create select for reasoning effort
  const {
    elements: { trigger: reasoningTrigger, menu: reasoningMenu, option: reasoningOption },
    states: { selected: reasoningSelected },
    helpers: { isSelected: isReasoningSelected }
  } = createSelect({
    defaultSelected: { value: reasoningEffort, label: reasoningEffortOptions.find(o => o.value === reasoningEffort)?.label || "Medium" },
    positioning: {
      placement: "bottom",
      fitViewport: true,
      sameWidth: true
    },
    portal: null,
    onSelectedChange: ({ next }) => {
      if (squelchReasoningEffort) return next;
      if (next?.value) {
        // Emit event to parent instead of mutating props
        dispatch("kwargsChange", { reasoning_effort: next.value });
      }
      return next;
    }
  });
  
  // Keep UI in sync with prop (read-only) - use squelch to prevent loops
  $: if (reasoningEffort && $reasoningSelected?.value !== reasoningEffort) {
    squelchOneTick((val) => squelchReasoningEffort = val);
    $reasoningSelected = { 
      value: reasoningEffort, 
      label: reasoningEffortOptions.find(o => o.value === reasoningEffort)?.label || "Medium" 
    };
  }
  
  // Create select for verbosity
  const {
    elements: { trigger: verbosityTrigger, menu: verbosityMenu, option: verbosityOption },
    states: { selected: verbositySelected },
    helpers: { isSelected: isVerbositySelected }
  } = createSelect({
    defaultSelected: { value: verbosity, label: verbosityOptions.find(o => o.value === verbosity)?.label || "Medium" },
    positioning: {
      placement: "bottom",
      fitViewport: true,
      sameWidth: true
    },
    portal: null,
    onSelectedChange: ({ next }) => {
      if (squelchVerbosity) return next;
      if (next?.value) {
        // Emit event to parent instead of mutating props
        dispatch("kwargsChange", { verbosity: next.value });
      }
      return next;
    }
  });
  
  // Keep UI in sync with prop (read-only) - use squelch to prevent loops
  $: if (verbosity && $verbositySelected?.value !== verbosity) {
    squelchOneTick((val) => squelchVerbosity = val);
    $verbositySelected = { 
      value: verbosity, 
      label: verbosityOptions.find(o => o.value === verbosity)?.label || "Medium" 
    };
  }

  // Create select for reasoning summary
  const {
    elements: { trigger: summaryTrigger, menu: summaryMenu, option: summaryOption },
    states: { selected: summarySelected },
    helpers: { isSelected: isSummarySelected }
  } = createSelect({
    defaultSelected: { value: reasoningSummary, label: reasoningSummaryOptions.find(o => o.value === reasoningSummary)?.label || "Disabled" },
    positioning: {
      placement: "bottom",
      fitViewport: true,
      sameWidth: true
    },
    portal: null,
    onSelectedChange: ({ next }) => {
      if (squelchSummary) return next;
      if (next?.value) {
        // Emit event to parent instead of mutating props
        dispatch("kwargsChange", { reasoning_summary: next.value });
      }
      return next;
    }
  });
  
  // Keep UI in sync with prop (read-only) - use squelch to prevent loops
  $: if (reasoningSummary && $summarySelected?.value !== reasoningSummary) {
    squelchOneTick((val) => squelchSummary = val);
    $summarySelected = { 
      value: reasoningSummary, 
      label: reasoningSummaryOptions.find(o => o.value === reasoningSummary)?.label || "Disabled" 
    };
  }
</script>

<!-- Reasoning Effort Setting -->
<div class="border-default hover:bg-hover-stronger flex h-[4.125rem] items-center justify-between gap-8 border-b px-4">
  <div class="flex items-center gap-2">
    <p class="w-24" aria-label="Reasoning effort setting">Reasoning Effort</p>
    <Tooltip
      text="Controls how many reasoning tokens the model generates before producing a response. Higher effort means more thorough reasoning but slower responses."
    >
      <IconQuestionMark class="text-muted hover:text-primary" />
    </Tooltip>
  </div>
  
  <button
    {...$reasoningTrigger}
    use:reasoningTrigger
    disabled={isDisabled}
    class:hover:cursor-default={isDisabled}
    class:text-secondary={isDisabled}
    class="border-default hover:bg-hover-default flex h-12 w-48 items-center justify-between rounded-lg border px-3"
  >
    <span class="capitalize">{$reasoningSelected?.label ?? "Medium"}</span>
    <IconChevronDown />
  </button>
  
  <div
    class="border-stronger bg-primary z-20 flex flex-col overflow-y-auto rounded-lg border shadow-xl"
    {...$reasoningMenu}
    use:reasoningMenu
  >
    <div class="bg-frosted-glass-secondary border-default sticky top-0 border-b px-4 py-2 font-mono text-sm">
      Select reasoning effort
    </div>
    {#each reasoningEffortOptions as option (option.value)}
      <div
        class="border-default hover:bg-hover-stronger flex min-h-16 items-center justify-between border-b px-4 hover:cursor-pointer"
        {...$reasoningOption({ value: option.value, label: option.label })}
        use:reasoningOption
      >
        <div>
          <span class="font-medium">{option.label}</span>
          <p class="text-muted text-sm">{option.description}</p>
        </div>
        <div class="check {$isReasoningSelected(option.value) ? 'block' : 'hidden'}">
          <IconCheck class="text-positive-default" />
        </div>
      </div>
    {/each}
  </div>
</div>

<!-- Verbosity Setting -->
<div class="border-default hover:bg-hover-stronger flex h-[4.125rem] items-center justify-between gap-8 border-b px-4">
  <div class="flex items-center gap-2">
    <p class="w-24" aria-label="Verbosity setting">Verbosity</p>
    <Tooltip
      text="Determines how many output tokens are generated. Lower verbosity reduces latency with more concise answers."
    >
      <IconQuestionMark class="text-muted hover:text-primary" />
    </Tooltip>
  </div>
  
  <button
    {...$verbosityTrigger}
    use:verbosityTrigger
    disabled={isDisabled}
    class:hover:cursor-default={isDisabled}
    class:text-secondary={isDisabled}
    class="border-default hover:bg-hover-default flex h-12 w-48 items-center justify-between rounded-lg border px-3"
  >
    <span class="capitalize">{$verbositySelected?.label ?? "Medium"}</span>
    <IconChevronDown />
  </button>
  
  <div
    class="border-stronger bg-primary z-20 flex flex-col overflow-y-auto rounded-lg border shadow-xl"
    {...$verbosityMenu}
    use:verbosityMenu
  >
    <div class="bg-frosted-glass-secondary border-default sticky top-0 border-b px-4 py-2 font-mono text-sm">
      Select verbosity level
    </div>
    {#each verbosityOptions as option (option.value)}
      <div
        class="border-default hover:bg-hover-stronger flex min-h-16 items-center justify-between border-b px-4 hover:cursor-pointer"
        {...$verbosityOption({ value: option.value, label: option.label })}
        use:verbosityOption
      >
        <div>
          <span class="font-medium">{option.label}</span>
          <p class="text-muted text-sm">{option.description}</p>
        </div>
        <div class="check {$isVerbositySelected(option.value) ? 'block' : 'hidden'}">
          <IconCheck class="text-positive-default" />
        </div>
      </div>
    {/each}
  </div>
</div>

<!-- Reasoning Summary Setting -->
<div class="border-default hover:bg-hover-stronger flex h-[4.125rem] items-center justify-between gap-8 border-b px-4">
  <div class="flex items-center gap-2">
    <p class="w-24" aria-label="Reasoning summary setting">Reasoning Summary</p>
    <Tooltip
      text="Controls whether the model provides a summary of its reasoning process. Useful for understanding how the model arrived at its response."
    >
      <IconQuestionMark class="text-muted hover:text-primary" />
    </Tooltip>
  </div>
  
  <button
    {...$summaryTrigger}
    use:summaryTrigger
    disabled={isDisabled}
    class:hover:cursor-default={isDisabled}
    class:text-secondary={isDisabled}
    class="border-default hover:bg-hover-default flex h-12 w-48 items-center justify-between rounded-lg border px-3"
  >
    <span class="capitalize">{$summarySelected?.label ?? "Disabled"}</span>
    <IconChevronDown />
  </button>
  
  <div
    class="border-stronger bg-primary z-20 flex flex-col overflow-y-auto rounded-lg border shadow-xl"
    {...$summaryMenu}
    use:summaryMenu
  >
    <div class="bg-frosted-glass-secondary border-default sticky top-0 border-b px-4 py-2 font-mono text-sm">
      Select reasoning summary
    </div>
    {#each reasoningSummaryOptions as option (option.value)}
      <div
        class="border-default flex min-h-16 items-center justify-between border-b px-4
               {option.disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-hover-stronger hover:cursor-pointer'}"
        {...(option.disabled ? {} : $summaryOption({ value: option.value, label: option.label }))}
        use:summaryOption
      >
        <div>
          <span class="font-medium {option.disabled ? 'text-muted' : ''}">{option.label}</span>
          <p class="text-muted text-sm">{option.description}</p>
        </div>
        <div class="check {$isSummarySelected(option.value) ? 'block' : 'hidden'}">
          <IconCheck class="text-positive-default" />
        </div>
      </div>
    {/each}
  </div>
</div>

<style lang="postcss">
  @reference "@intric/ui/styles";
  div[data-highlighted] {
    @apply bg-hover-default;
  }

  div[data-disabled] {
    @apply opacity-30 hover:bg-transparent;
  }
</style>