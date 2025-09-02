<script lang="ts">
  import type { AriaProps } from "$lib/core/AriaUtils";
  import {
    behaviourList,
    getBehaviour,
    getKwargs,
    type ModelBehaviour,
    type ModelKwArgs
  } from "../ModelBehaviours";
  import { supportsGpt5Settings } from "../supportsGpt5Settings";
  import { createSelect } from "@melt-ui/svelte";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { IconCheck } from "@intric/icons/check";
  import { IconQuestionMark } from "@intric/icons/question-mark";
  import { Input, Tooltip } from "@intric/ui";
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  export let kwArgs: ModelKwArgs;
  export let isDisabled: boolean;
  export let modelName: string | undefined = undefined;
  export let aria: AriaProps = { "aria-label": "Select model behaviour" };

  // helper: keep only defined keys
  function pickDefined<T extends Record<string, any>>(obj: T) {
    return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined)) as Partial<T>;
  }

  const {
    elements: { trigger, menu, option },
    helpers: { isSelected },
    states: { selected }
  } = createSelect<ModelBehaviour>({
    defaultSelected: { value: getBehaviour(kwArgs) },
    positioning: {
      placement: "bottom",
      fitViewport: true,
      sameWidth: true
    },
    portal: null,
    onSelectedChange: ({ next }) => {
      const selectedBehaviour = next?.value;
      
      // What the behaviour preset wants (usually temperature / top_p)
      const behaviourArgs = selectedBehaviour ? getKwargs(selectedBehaviour) : getKwargs("default");
      
      // Fallback for "custom"
      const defaultTemp = supportsGpt5Settings(modelName) ? 1.0 : 1;
      const customArgs =
        getBehaviour(kwArgs) === "custom" ? kwArgs : { temperature: defaultTemp, top_p: null };
      
      // Start from behaviour (or custom) args
      let patch = behaviourArgs ?? customArgs;
      
      if (supportsGpt5Settings(modelName)) {
        // Preserve existing GPT-5 fields (do not override them)
        patch = {
          ...patch,
          temperature: 1.0,
          reasoning_effort: kwArgs?.reasoning_effort,
          verbosity: kwArgs?.verbosity,
          reasoning_summary: kwArgs?.reasoning_summary
        };
      }
      
      // Emit patch to parent instead of mutating kwArgs
      dispatch("kwargsChange", patch);
      return next;
    }
  });

  // This function will only be called on direct user input of custom temperature
  // If the selected value is not a named value, it will emit a patch
  // This can't be a declarative statement with $: as it would fire in too many situations
  let customTemp: number = 1;
  function maybeSetKwArgsCustom() {
    // For GPT-5 models, temperature is locked to 1.0
    if (supportsGpt5Settings(modelName)) {
      customTemp = 1.0;
      return;
    }
    
    const args = { temperature: customTemp, top_p: null };
    if (getBehaviour(args) === "custom") {
      // Emit patch instead of mutating
      dispatch("kwargsChange", args);
    }
  }

  function watchChanges(currentKwArgs: ModelKwArgs) {
    if (isDisabled) {
      $selected = { value: "default" };
      return;
    }

    // DON'T modify kwArgs here for GPT-5 temperature!
    // This causes infinite loops. The temperature should be
    // enforced when the user selects a behavior, not in the watcher.
    
    const behaviour = getBehaviour(currentKwArgs);

    if ($selected?.value !== behaviour) {
      $selected = { value: behaviour };
    }

    if (
      behaviour === "custom" &&
      currentKwArgs.temperature &&
      currentKwArgs.temperature !== customTemp
    ) {
      customTemp = currentKwArgs.temperature;
    }
  }

  $: watchChanges(kwArgs);
</script>

<button
  {...$trigger}
  {...aria}
  use:trigger
  disabled={isDisabled}
  class:hover:cursor-default={isDisabled}
  class:text-secondary={isDisabled}
  class="border-default hover:bg-hover-default flex h-16 items-center justify-between border-b px-4"
>
  <span class="capitalize">{$selected?.value ?? "No behaviour found"}</span>
  <IconChevronDown />
</button>

<div
  class="border-stronger bg-primary z-20 flex flex-col overflow-y-auto rounded-lg border shadow-xl"
  {...$menu}
  use:menu
>
  <div
    class="bg-frosted-glass-secondary border-default sticky top-0 border-b px-4 py-2 font-mono text-sm"
  >
    Select a model behaviour
  </div>
  {#each behaviourList as behavior (behavior)}
    <div
      class="border-default hover:bg-hover-stronger flex min-h-16 items-center justify-between border-b px-4 hover:cursor-pointer"
      {...$option({ value: behavior })}
      use:option
    >
      <span class="capitalize">
        {behavior}
      </span>
      <div class="check {$isSelected(behavior) ? 'block' : 'hidden'}">
        <IconCheck class="text-positive-default" />
      </div>
    </div>
  {/each}
</div>

{#if $selected?.value === "custom"}
  <div
    class="border-default hover:bg-hover-stronger flex h-[4.125rem] items-center justify-between gap-8 border-b px-4"
  >
    <div class="flex items-center gap-2">
      <p class="w-24" aria-label="Temperature setting" id="temperature_label">Temperature</p>
      <Tooltip
        text={supportsGpt5Settings(modelName) 
          ? "Temperature is fixed at 1.0 for GPT-5 models and cannot be changed." 
          : "Randomness: A value between 0 and 2 (Default: 1)\nHigher values will create more creative responses.\nLower values will be more deterministic."}
      >
        <IconQuestionMark class="text-muted hover:text-primary" />
      </Tooltip>
    </div>
    <Input.Slider
      bind:value={customTemp}
      max={2}
      min={0}
      step={0.01}
      onInput={maybeSetKwArgsCustom}
    />
    <Input.Number
      onInput={maybeSetKwArgsCustom}
      bind:value={customTemp}
      step={0.01}
      max={2}
      min={0}
      disabled={supportsGpt5Settings(modelName)}
      hiddenLabel={true}
    ></Input.Number>
  </div>
{/if}

{#if isDisabled}
  <p
    class="label-warning border-label-default bg-label-dimmer text-label-stronger mt-2.5 rounded-md border px-2 py-1 text-sm"
  >
    <span class="font-bold">Warning:&nbsp;</span>Temperature settings not available for this model.
  </p>
{:else if supportsGpt5Settings(modelName) && $selected?.value === "custom"}
  <p
    class="label-info border-label-default bg-label-dimmer text-label-stronger mt-2.5 rounded-md border px-2 py-1 text-sm"
  >
    <span class="font-bold">Info:&nbsp;</span>Temperature is fixed at 1.0 for GPT-5 models and cannot be modified.
  </p>
{/if}

<style lang="postcss">
  @reference "@intric/ui/styles";
  div[data-highlighted] {
    @apply bg-hover-default;
  }

  /* div[data-selected] { } */

  div[data-disabled] {
    @apply opacity-30 hover:bg-transparent;
  }
</style>
