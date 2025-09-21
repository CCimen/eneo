<script lang="ts">
  import { IconCheck } from "@intric/icons/check";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { IconEdit } from "@intric/icons/edit";
  import { IconFileImage } from "@intric/icons/file-image";
  import { createSelect } from "@melt-ui/svelte";
  import type { ComponentType } from "svelte";

  type OutputType = "text" | "image";

  export let value: OutputType = "text";
  export let aria: AriaProps;

  const outputTypes: Record<OutputType, { icon: ComponentType; label: string }> = {
    text: { icon: IconEdit, label: "Text completion" },
    image: { icon: IconFileImage, label: "Image generation" }
  };

  const {
    elements: { trigger, menu, option },
    states: { selected },
    helpers: { isSelected }
  } = createSelect<OutputType>({
    positioning: {
      placement: "bottom",
      fitViewport: true,
      sameWidth: true
    },
    defaultSelected: { value },
    portal: null,
    onSelectedChange: ({ next }) => {
      value = next?.value ?? value;
      return next;
    }
  });

  function watchChanges(value: OutputType) {
    if ($selected?.value !== value) {
      $selected = { value };
    }
  }
  // Watch outside changes
  $: watchChanges(value);
</script>

<button
  {...$trigger}
  {...aria}
  use:trigger
  class="border-default hover:bg-hover-dimmer flex h-16 items-center justify-between border-b px-4"
>
  {#if $selected}
    <div class="flex items-center gap-3">
      <svelte:component this={outputTypes[$selected.value].icon}></svelte:component>
      <span>{outputTypes[$selected.value].label}</span>
    </div>
  {:else}
    Nothing selected
  {/if}
  <IconChevronDown />
</button>

<div
  class="border-stronger bg-primary z-20 flex flex-col overflow-y-auto rounded-lg border shadow-xl"
  {...$menu}
  use:menu
>
  {#each Object.entries(outputTypes) as [outputType, { icon, label }] (outputType)}
    <div
      class="border-default hover:bg-hover-default flex min-h-16 items-center justify-between border-b px-4 last-of-type:border-b-0 hover:cursor-pointer"
      {...$option({ value: outputType })}
      use:option
    >
      <div class="flex items-center gap-3">
        <svelte:component this={icon}></svelte:component>
        <span>{label}</span>
      </div>
      <div class="check {$isSelected(outputType) ? 'block' : 'hidden'}">
        <IconCheck class="text-positive-default !size-8"></IconCheck>
      </div>
    </div>
  {/each}
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