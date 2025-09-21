<script lang="ts">
  import { Settings } from "$lib/components/layout";
  import { getAppEditor } from "$lib/features/apps/AppEditor";
  import { getSpacesManager } from "$lib/features/spaces/SpacesManager.js";
  import AppSettingsOutputType from "./AppSettingsOutputType.svelte";
  import SelectAIModelV2 from "$lib/features/ai-models/components/SelectAIModelV2.svelte";

  const {
    state: { resource, update, currentChanges },
    discardChanges
  } = getAppEditor();

  const {
    state: { currentSpace }
  } = getSpacesManager();

  // When output type is image, ensure the model is a proper object, not just a string
  $: if ($update.output_type === "image" && $currentSpace.image_generation_models?.length > 0) {
    // Check if image_generation_model is not set, or is a string (not an object with an id)
    if (!$update.image_generation_model || typeof $update.image_generation_model === 'string' || !$update.image_generation_model.id) {
      // Set to first available image generation model
      $update.image_generation_model = $currentSpace.image_generation_models[0];
    }
  }
</script>

<Settings.Row
  title="Output type"
  description="Select whether this app generates text completions or images."
  hasChanges={$currentChanges.diff.output_type !== undefined}
  revertFn={() => {
    discardChanges("output_type");
  }}
  let:aria
>
  <AppSettingsOutputType bind:value={$update.output_type} {aria}></AppSettingsOutputType>
</Settings.Row>

{#if $update.output_type === "image"}
  <Settings.Row
    title="Image generation model"
    description="This model will be used to generate images from prompts."
    hasChanges={$currentChanges.diff.image_generation_model !== undefined}
    revertFn={() => {
      discardChanges("image_generation_model");
    }}
    let:aria
  >
    <SelectAIModelV2
      bind:selectedModel={$update.image_generation_model}
      availableModels={$currentSpace.image_generation_models || []}
      {aria}
    ></SelectAIModelV2>
  </Settings.Row>
{/if}