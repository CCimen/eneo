<script lang="ts">
  import { IconDownload } from "@intric/icons/download";
  import { IconCopy } from "@intric/icons/copy";
  import { IconXMark } from "@intric/icons/x-mark";
  import { IconCheck } from "@intric/icons/check";
  import { IconChevronDown } from "@intric/icons/chevron-down";
  import { Button, Dialog, Tooltip } from "@intric/ui";
  import { writable } from "svelte/store";
  import { fly, fade, scale } from "svelte/transition";
  import { cubicOut } from "svelte/easing";

  type Props = {
    url: string | null;
    metadata?: {
      size?: string;
      prompt?: string;
      fileSize?: number;
      model?: string;
      seed?: string;
      steps?: number;
    };
    variant?: "chat" | "app";
  };

  const { url, metadata, variant = "chat" }: Props & { variant?: "chat" | "app" } = $props();

  let imageLoaded = $state(false);
  let imageError = $state(false);
  let imageDimensions = $state<{ width: number; height: number } | null>(null);
  let imageFileSize = $state<number>(0);
  let copiedIcon = $state(false);
  let downloadedToast = $state(false);
  let chatPromptVisible = $state(false);
  let lastUrl = $state<string | null>(url);
  const promptPanelId = `async-image-prompt-${
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2, 10)
  }`;

  const promptLength = $derived(metadata?.prompt?.length ?? 0);
  const chatPromptNeedsScroll = $derived(promptLength > 420);
  const modalPromptNeedsScroll = $derived(promptLength > 600);

  const dialogOpenStore = writable(false);

  const parseDimensions = (size?: string | null) => {
    if (!size) return null;
    const match = size.match(/(\d+)[^\d]+(\d+)/);
    if (!match) return null;
    const width = Number(match[1]);
    const height = Number(match[2]);
    if (!width || !height) return null;
    return { width, height };
  };

  const getAspectRatio = (dimensions?: { width: number; height: number } | null) => {
    if (!dimensions || !dimensions.width || !dimensions.height) return 1;
    return Number((dimensions.width / dimensions.height).toFixed(3));
  };

  let aspectRatio = $state(getAspectRatio(parseDimensions(metadata?.size)));

  const fallbackDimensions = $derived.by(() => imageDimensions ?? parseDimensions(metadata?.size));
  const currentFileSize = $derived(imageFileSize || metadata?.fileSize || 0);

  const modalInfoItems = $derived.by(() => {
    const items: { label: string; value: string }[] = [];
    if (fallbackDimensions) {
      items.push({ label: "Dimensions", value: `${fallbackDimensions.width}×${fallbackDimensions.height}` });
    }
    if (currentFileSize) {
      items.push({ label: "File size", value: formatFileSize(currentFileSize) });
    }
    if (metadata?.model) {
      items.push({ label: "Model", value: metadata.model });
    }
    if (metadata?.seed) {
      items.push({ label: "Seed", value: metadata.seed });
    }
    if (typeof metadata?.steps === "number") {
      items.push({ label: "Steps", value: String(metadata.steps) });
    }
    return items;
  });

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  const copyPrompt = async () => {
    if (metadata?.prompt) {
      await navigator.clipboard.writeText(metadata.prompt);
      copiedIcon = true;
      setTimeout(() => (copiedIcon = false), 2000);
    }
  };

  const downloadImage = () => {
    if (url) {
      const link = document.createElement("a");
      link.href = url;
      link.download = "generated-image.png";
      link.click();
      downloadedToast = true;
      setTimeout(() => (downloadedToast = false), 2000);
    }
  };

  $effect(() => {
    if (url !== lastUrl) {
      imageLoaded = false;
      imageError = false;
      imageDimensions = null;
      if (!metadata?.fileSize) {
        imageFileSize = 0;
      }
      lastUrl = url;
    }
  });

  $effect(() => {
    if (url && !metadata?.fileSize && !imageFileSize) {
      fetch(url)
        .then((response) => {
          const contentLength = response.headers.get("content-length");
          if (contentLength) {
            imageFileSize = parseInt(contentLength, 10);
          }
        })
        .catch(() => {});
    }
  });

  $effect(() => {
    aspectRatio = getAspectRatio(fallbackDimensions);
  });

  $effect(() => {
    if ($dialogOpenStore) {
      const handleKeydown = (e: KeyboardEvent) => {
        if (e.key === "Escape") dialogOpenStore.set(false);
        if (e.key === "c" && (e.metaKey || e.ctrlKey)) copyPrompt();
      };
      window.addEventListener("keydown", handleKeydown);
      return () => window.removeEventListener("keydown", handleKeydown);
    }
  });
</script>

<Dialog.Root openController={dialogOpenStore}>
  {#if variant === "app"}
    <div class="mx-auto w-full max-w-3xl">
      <div class="rounded-[32px] border border-default/70 bg-primary shadow-lg overflow-hidden">
        <div class="px-6 py-6 sm:px-9 sm:py-9">
            <button
            type="button"
            class="group relative block w-full rounded-3xl text-left transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-default disabled:cursor-not-allowed disabled:opacity-70"
            onclick={() => imageLoaded && url && dialogOpenStore.set(true)}
            disabled={!imageLoaded || !url}
            aria-label="Open image preview"
            >
                <div
                    class="relative w-full overflow-hidden rounded-3xl border border-default bg-primary shadow-md transition-[border-color,box-shadow,transform] duration-300 group-hover:border-accent-stronger group-hover:shadow-xl"
                    style={`aspect-ratio: ${aspectRatio || 1}; max-height: min(70vh, 680px);`}
                >
                    {#if url}
                    <img
                        src={url}
                        class="absolute inset-0 h-full w-full transform object-contain transition-opacity transition-transform duration-300 ease-out group-hover:scale-[1.015] group-hover:duration-500"
                        class:opacity-0={!imageLoaded || imageError}
                        class:opacity-100={imageLoaded && !imageError}
                        onload={(event) => {
                        const img = event.currentTarget as HTMLImageElement;
                        if (img?.naturalWidth && img?.naturalHeight) {
                            imageDimensions = { width: img.naturalWidth, height: img.naturalHeight };
                        }
                        imageLoaded = true;
                        imageError = false;
                        }}
                        onerror={() => {
                        imageError = true;
                        imageLoaded = false;
                        }}
                        alt="Generated image"
                        draggable="false"
                    />
                    {/if}

                    {#if imageError}
                    <div class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-secondary/8">
                        <p class="text-sm font-medium text-secondary">Failed to load image</p>
                    </div>
                    {/if}

                    {#if !url || (!imageLoaded && !imageError)}
                    <div class="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-secondary/10">
                        <div class="h-12 w-12 animate-pulse rounded-full bg-secondary/25" />
                        <p class="text-xs uppercase tracking-[0.2em] text-secondary">Generating image...</p>
                    </div>
                    {/if}

                    {#if imageLoaded && !imageError}
                    <div class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/10">
                        <span class="rounded-full bg-black/60 px-4 py-1.5 text-xs font-medium text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                        Click to expand
                        </span>
                    </div>
                    {/if}
                </div>
            </button>

            {#if imageLoaded && !imageError}
            <div class="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                {#if fallbackDimensions || currentFileSize}
                <div class="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-secondary/80">
                    {#if fallbackDimensions}
                    <span class="flex items-center gap-2">
                        <span class="font-medium text-secondary/70">Size</span>
                        <span class="font-semibold text-primary">{fallbackDimensions.width}×{fallbackDimensions.height}</span>
                    </span>
                    {/if}
                    {#if fallbackDimensions && currentFileSize}
                    <span aria-hidden="true" class="h-3 w-px bg-secondary/30" />
                    {/if}
                    {#if currentFileSize}
                    <span class="flex items-center gap-2">
                        <span class="font-medium text-secondary/70">File</span>
                        <span class="font-semibold text-primary">{formatFileSize(currentFileSize)}</span>
                    </span>
                    {/if}
                </div>
                {/if}
                <Button
                variant="primary"
                padding="icon-leading"
                onclick={downloadImage}
                class="w-full gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-transform duration-200 hover:-translate-y-[1px] sm:w-auto"
                >
                <IconDownload class="h-4 w-4" />
                Download
                </Button>
            </div>
            {/if}
        </div>
        {#if metadata?.prompt}
            <div class="border-t border-default/70 bg-primary/80 px-6 py-5 sm:px-9">
                <h3 class="text-[11px] font-semibold uppercase tracking-[0.2em] text-secondary">Prompt</h3>
                <p class="mt-2 text-base leading-relaxed text-primary">{metadata.prompt}</p>
            </div>
        {/if}
      </div>
    </div>
  {:else}
    <div class="w-full" style="max-width: min(620px, 100%);">
      <div class="bg-primary border border-default rounded-2xl shadow-sm overflow-hidden">
        {#if metadata?.prompt}
          <div class="flex items-center justify-between px-4 pt-3 pb-2 sm:px-5 sm:pt-4">
            <Tooltip content={chatPromptVisible ? "Hide prompt" : "Show prompt"} placement="bottom">
              <Button
                type="button"
                variant="simple"
                padding="icon-leading"
                class={`flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] transition-colors ${chatPromptVisible ? 'text-primary' : 'text-secondary'}`}
                aria-expanded={chatPromptVisible}
                aria-controls={promptPanelId}
                onclick={() => (chatPromptVisible = !chatPromptVisible)}
              >
                <span>{chatPromptVisible ? "Hide Prompt" : "Show Prompt"}</span>
                <IconChevronDown
                  class={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${
                    chatPromptVisible ? "rotate-180" : ""
                  }`}
                />
              </Button>
            </Tooltip>
            <Tooltip content={copiedIcon ? "Copied!" : "Copy prompt"}>
              <Button
                type="button"
                variant="simple"
                padding="icon"
                class={`rounded-lg p-2 text-[11px] font-medium transition-colors hover:text-primary ${copiedIcon ? 'text-positive-stronger' : 'text-secondary'}`}
                onclick={copyPrompt}
                aria-label="Copy prompt"
              >
                {#if copiedIcon}
                  <IconCheck class="h-4 w-4 text-positive-stronger" />
                {:else}
                  <IconCopy class="h-4 w-4" />
                {/if}
              </Button>
            </Tooltip>
          </div>
          {#if chatPromptVisible}
            <div
              id={promptPanelId}
              class={`px-4 pb-3 sm:px-5 ${
                chatPromptNeedsScroll ? "max-h-[40vh] overflow-y-auto pr-1 sm:pr-2" : ""
              }`}
              in:fade={{ duration: 150 }}
              out:fade={{ duration: 120 }}
            >
              <p class="whitespace-pre-wrap text-sm leading-relaxed text-primary">
                {metadata.prompt}
              </p>
            </div>
          {/if}
        {/if}

        <button
          type="button"
          class="group relative block w-full text-left transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-default disabled:cursor-not-allowed disabled:opacity-70"
          class:rounded-t-none={metadata?.prompt}
          class:rounded-2xl={!metadata?.prompt}
          onclick={() => imageLoaded && url && dialogOpenStore.set(true)}
          disabled={!imageLoaded || !url}
          aria-label="Open image preview"
        >
          <div
            class="relative w-full overflow-hidden border-t border-default bg-primary transition-[border-color,box-shadow] duration-300 group-hover:border-accent-default group-hover:shadow-lg"
            class:rounded-b-2xl={true}
            style={`aspect-ratio: ${aspectRatio || 1}; max-height: min(60vh, 540px);`}
          >
            {#if url}
              <img
                src={url}
                class="absolute inset-0 h-full w-full transform object-contain transition-opacity transition-transform duration-300 ease-out group-hover:scale-[1.01] group-hover:duration-500"
                class:opacity-0={!imageLoaded || imageError}
                class:opacity-100={imageLoaded && !imageError}
                onload={(event) => {
                  const img = event.currentTarget as HTMLImageElement;
                  if (img?.naturalWidth && img?.naturalHeight) {
                    imageDimensions = { width: img.naturalWidth, height: img.naturalHeight };
                  }
                  imageLoaded = true;
                  imageError = false;
                }}
                onerror={() => {
                  imageError = true;
                  imageLoaded = false;
                }}
                alt="Generated image"
                draggable="false"
              />
            {/if}

            {#if imageError}
              <div class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-secondary/5">
                <p class="text-sm font-medium text-secondary">Failed to load image</p>
              </div>
            {/if}

            {#if !url || (!imageLoaded && !imageError)}
              <div class="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-secondary/10">
                <div class="h-10 w-10 animate-pulse rounded-full bg-secondary/25"></div>
                <p class="text-[11px] uppercase tracking-wide text-secondary">Generating image...</p>
              </div>
            {/if}

            {#if imageLoaded && !imageError}
              <div class="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 transition-colors group-hover:bg-black/10">
                <span class="rounded-full bg-black/60 px-3 py-1 text-xs font-medium text-white opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                  Click to expand
                </span>
              </div>
            {/if}
          </div>
        </button>

        {#if imageLoaded && !imageError}
          <div class="flex items-center justify-between px-4 py-3 sm:px-5 sm:py-4 border-t border-default/60">
            {#if fallbackDimensions || currentFileSize}
              <div class="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-secondary">
                {#if fallbackDimensions}
                  <span class="flex items-center gap-1">
                    <span class="font-medium text-secondary/70">Size</span>
                    <span class="font-semibold text-primary">{fallbackDimensions.width}×{fallbackDimensions.height}</span>
                  </span>
                {/if}
                {#if fallbackDimensions && currentFileSize}
                  <span aria-hidden="true" class="mx-1 h-2 w-px bg-secondary/40"></span>
                {/if}
                {#if currentFileSize}
                  <span class="flex items-center gap-1">
                    <span class="font-medium text-secondary/70">File</span>
                    <span class="font-semibold text-primary">{formatFileSize(currentFileSize)}</span>
                  </span>
                {/if}
              </div>
            {/if}
            <Button
              variant="primary"
              padding="icon-leading"
              onclick={downloadImage}
              class="gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition-all duration-200 hover:-translate-y-[1px]"
            >
              <IconDownload class="h-4 w-4" />
              Download
            </Button>
          </div>
        {/if}
      </div>
    </div>
  {/if}

  <Dialog.Content width="large" class="!border-none !bg-transparent !p-0">
    {#if url && imageLoaded && !imageError}
      <div
        class="relative flex max-h-[85vh] flex-col overflow-hidden rounded-3xl bg-primary shadow-2xl ring-1 ring-default/50 lg:flex-row"
        in:scale={{ start: 0.95, duration: 220, easing: cubicOut }}
        out:fade={{ duration: 180, easing: cubicOut }}
      >
        <div class="flex flex-1 items-center justify-center bg-secondary/10 p-4 sm:p-6 md:p-8">
          <img
            src={url}
            class="max-h-[75vh] w-auto max-w-full object-contain"
            alt="Generated image"
            draggable="false"
          />
        </div>

        <aside class="flex w-full flex-col gap-6 border-t border-default bg-primary px-6 py-6 lg:w-[380px] lg:flex-shrink-0 lg:border-l lg:border-t-0 lg:py-8">
          <div class="flex items-center justify-end">
            <button
              type="button"
              onclick={() => dialogOpenStore.set(false)}
              class="flex h-9 w-9 items-center justify-center rounded-full border border-transparent text-secondary transition-colors hover:border-dimmer hover:bg-hover-default hover:text-primary"
              aria-label="Close"
            >
              <IconXMark class="h-4 w-4" />
            </button>
          </div>

          {#if modalInfoItems.length}
            <div class="space-y-3">
              <h3 class="text-[11px] font-semibold uppercase tracking-[0.2em] text-secondary">Details</h3>
              <dl class="space-y-2 text-sm">
                {#each modalInfoItems as item (item.label)}
                  <div class="flex items-baseline justify-between gap-4">
                    <dt class="text-secondary">{item.label}</dt>
                    <dd class="font-medium text-primary">{item.value}</dd>
                  </div>
                {/each}
              </dl>
            </div>
          {/if}

          {#if metadata?.prompt}
            <div class="flex-grow space-y-3">
              <h3 class="text-[11px] font-semibold uppercase tracking-[0.2em] text-secondary">Prompt</h3>
              <div
                class={`rounded-xl border border-default bg-primary p-4 ${
                  modalPromptNeedsScroll ? "max-h-[50vh] overflow-y-auto pr-1 sm:pr-2" : ""
                }`}
              >
                <div class="flex items-center justify-end -mt-1 -mr-1 mb-2">
                  <Tooltip content={copiedIcon ? "Copied!" : "Copy prompt"}>
                    <Button
                      variant="simple"
                      padding="icon"
                      onclick={copyPrompt}
                      class={`h-8 w-8 rounded-lg text-secondary transition-colors hover:text-primary ${copiedIcon ? '!text-positive-stronger' : ''}`}
                      aria-label="Copy prompt"
                    >
                      {#if copiedIcon}
                        <IconCheck class="h-4 w-4" />
                      {:else}
                        <IconCopy class="h-4 w-4" />
                      {/if}
                    </Button>
                  </Tooltip>
                </div>
                <p class="whitespace-pre-wrap text-sm leading-relaxed text-primary">
                  {metadata.prompt}
                </p>
              </div>
            </div>
          {/if}
          
          <div class="mt-auto">
            <Button
                variant="primary"
                padding="icon-leading"
                onclick={downloadImage}
                class="gap-2 w-full"
            >
                <IconDownload class="h-4 w-4" />
                Download image
            </Button>
          </div>
        </aside>
      </div>
    {:else if url}
      <div
        class="flex max-h-[85vh] items-center justify-center rounded-3xl bg-primary p-16 shadow-2xl"
        in:scale={{ start: 0.95, duration: 220, easing: cubicOut }}
        out:fade={{ duration: 180, easing: cubicOut }}
      >
        <div class="h-12 w-12 animate-spin rounded-full border-2 border-dashed border-secondary"></div>
      </div>
    {/if}
  </Dialog.Content>
</Dialog.Root>

{#if downloadedToast}
  <div
    class="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg border border-default bg-primary px-4 py-3 shadow-lg"
    in:fly={{ y: 20, duration: 200 }}
    out:fade={{ duration: 200 }}
  >
    <IconDownload class="h-4 w-4 text-positive-stronger" />
    <span class="text-sm">Image downloaded</span>
  </div>
{/if}
