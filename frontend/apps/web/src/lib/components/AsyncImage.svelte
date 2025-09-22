<script lang="ts">
  import { IconDownload } from "@intric/icons/download";
  import { IconCopy } from "@intric/icons/copy";
  import { IconXMark } from "@intric/icons/x-mark";
  import { IconCheck } from "@intric/icons/check";
  import { Button, Dialog, Tooltip } from "@intric/ui";
  import { writable } from "svelte/store";
  import { fly, fade } from "svelte/transition";

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
  };

  const { url, metadata }: Props = $props();

  let imageLoaded = $state(false);
  let imageError = $state(false);
  let imageDimensions = $state<{ width: number; height: number } | null>(null);
  let imageFileSize = $state<number>(0);
  let promptExpanded = $state(false);
  let copiedIcon = $state(false);
  let downloadedToast = $state(false);
  let promptCollapsed = $state(false);

  const dialogOpenStore = writable(false);

  // Format file size for display
  const formatFileSize = (bytes: number) => {
    if (!bytes) return '';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // Copy prompt to clipboard with icon feedback
  const copyPrompt = async () => {
    if (metadata?.prompt) {
      await navigator.clipboard.writeText(metadata.prompt);
      copiedIcon = true;
      setTimeout(() => copiedIcon = false, 2000);
    }
  };

  // Download image with toast
  const downloadImage = () => {
    if (url) {
      const link = document.createElement('a');
      link.href = url;
      link.download = 'generated-image.png';
      link.click();
      downloadedToast = true;
      setTimeout(() => downloadedToast = false, 2000);
    }
  };

  // Fetch image to get file size
  $effect(() => {
    if (url && !imageFileSize) {
      fetch(url)
        .then(response => {
          const contentLength = response.headers.get('content-length');
          if (contentLength) {
            imageFileSize = parseInt(contentLength, 10);
          }
        })
        .catch(() => {});
    }
  });

  // Keyboard shortcuts in modal
  $effect(() => {
    if ($dialogOpenStore) {
      const handleKeydown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') dialogOpenStore.set(false);
        if (e.key === 'c' && (e.metaKey || e.ctrlKey)) copyPrompt();
      };
      window.addEventListener('keydown', handleKeydown);
      return () => window.removeEventListener('keydown', handleKeydown);
    }
  });
</script>

<Dialog.Root openController={dialogOpenStore}>
  <!-- Chat Message Card View - Compact sizing -->
  <div class="w-full max-w-[340px] sm:max-w-[380px] md:max-w-[420px] lg:max-w-[460px] xl:max-w-[480px] 2xl:max-w-[520px] bg-primary rounded-xl border border-default overflow-hidden">
    <!-- Prompt Header with Inline Copy -->
    {#if metadata?.prompt}
      <div class="px-3 pt-3 pb-2 sm:px-4 sm:pt-4 sm:pb-2 flex items-start justify-between gap-2">
        <div class="flex-1 min-w-0">
          <p class="text-xs sm:text-sm leading-relaxed text-primary {promptExpanded ? '' : 'line-clamp-2'}">
            {metadata.prompt}
          </p>
          {#if metadata.prompt.length > 150}
            <button
              onclick={() => promptExpanded = !promptExpanded}
              class="text-xs text-secondary hover:text-primary mt-1 transition-colors"
            >
              {promptExpanded ? 'Show less' : 'Show more'}
            </button>
          {/if}
        </div>
        <Tooltip content={copiedIcon ? "Copied!" : "Copy prompt"}>
          <button
            onclick={copyPrompt}
            class="p-1 sm:p-1.5 rounded-lg hover:bg-secondary/10 transition-colors flex-shrink-0"
            aria-label="Copy prompt"
          >
            {#if copiedIcon}
              <IconCheck class="h-3.5 w-3.5 sm:h-4 sm:w-4 text-green-500" />
            {:else}
              <IconCopy class="h-3.5 w-3.5 sm:h-4 sm:w-4 text-secondary hover:text-primary" />
            {/if}
          </button>
        </Tooltip>
      </div>
    {/if}

    <!-- Image Container -->
    <div class="px-3 pb-3 sm:px-4 sm:pb-4">
      <!-- Clickable Image -->
      <button
        type="button"
        class="relative w-full group cursor-pointer rounded-lg sm:rounded-xl overflow-hidden border border-default"
        onclick={() => dialogOpenStore.set(true)}
        aria-label="Click to view full size"
      >
        {#if !imageLoaded && !imageError && url}
          <!-- Better aspect ratio for loading state -->
          <div class="w-full aspect-[4/3] bg-secondary/5 animate-pulse" />
        {/if}

        {#if url}
          <img
            src={url}
            class="w-full h-auto max-h-[48vh] sm:max-h-[50vh] md:max-h-[52vh] lg:max-h-[54vh] object-contain block {imageLoaded ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300"
            onload={(e) => {
              imageLoaded = true;
              imageError = false;
              const img = e.target as HTMLImageElement;
              if (img) {
                imageDimensions = { width: img.naturalWidth, height: img.naturalHeight };
              }
            }}
            onerror={() => {
              imageError = true;
              imageLoaded = false;
            }}
            alt="Generated image"
          />
        {/if}

        {#if imageError}
          <div class="flex flex-col items-center justify-center p-12 bg-secondary/5">
            <p class="text-secondary">Failed to load image</p>
          </div>
        {/if}

        <!-- Hover overlay with expand hint -->
        {#if imageLoaded}
          <div class="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors flex items-center justify-center">
            <div class="opacity-0 group-hover:opacity-100 transition-opacity bg-black/60 text-white px-3 py-1.5 rounded-lg text-xs font-medium">
              Click to view
            </div>
          </div>
        {/if}
      </button>

      <!-- Download Action - Left aligned for better UX -->
      {#if imageLoaded}
        <div class="mt-3">
          <Button
            variant="primary"
            size="sm"
            onclick={downloadImage}
            class="gap-1.5 !px-3 !py-1.5 !text-xs sm:!text-sm"
          >
            <IconDownload class="h-3.5 w-3.5" />
            Download
          </Button>
        </div>
      {/if}
    </div>
  </div>

  <!-- Detail Modal - Matching image3.png Design -->
  <Dialog.Content class="!max-w-[720px] !w-[90vw] sm:!w-[80vw] md:!w-[70vw] lg:!w-[60vw] xl:!max-w-[720px] 2xl:!w-[50vw] !rounded-2xl overflow-hidden shadow-2xl bg-white !max-h-[85vh]">
    <div class="relative flex flex-col max-h-[85vh]">
      {#if url && imageLoaded}
        <!-- Close button -->
        <button
          onclick={() => dialogOpenStore.set(false)}
          class="absolute top-3 right-3 sm:top-4 sm:right-4 z-10 p-1.5 sm:p-2 rounded-lg bg-white/90 hover:bg-white transition-colors shadow-md"
          aria-label="Close"
        >
          <IconXMark class="h-4 w-4 sm:h-5 sm:w-5 text-gray-700" />
        </button>

        <!-- Image container -->
        <div class="bg-gray-50 p-4 sm:p-6 md:p-8 2xl:p-10 flex items-center justify-center flex-shrink-0">
          <img
            src={url}
            class="max-w-full max-h-[40vh] sm:max-h-[45vh] md:max-h-[50vh] lg:max-h-[55vh] 2xl:max-h-[50vh] object-contain rounded-lg shadow-lg"
            alt="Generated image"
          />
        </div>

        <!-- Details section below image -->
        <div class="bg-white px-4 py-4 sm:px-6 sm:py-5 md:px-8 md:py-6 2xl:px-10 2xl:py-7 flex-shrink-0">
          <!-- Inline metadata and download button -->
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
            <div class="flex flex-wrap items-center gap-3 sm:gap-5 text-xs sm:text-sm text-gray-600">
              {#if imageDimensions}
                <span class="whitespace-nowrap">
                  <span class="text-gray-500">Dimensions:</span>
                  <span class="ml-1 font-medium text-gray-800">{imageDimensions.width}×{imageDimensions.height}</span>
                </span>
              {/if}
              {#if imageFileSize}
                <span class="whitespace-nowrap">
                  <span class="text-gray-500">File size:</span>
                  <span class="ml-1 font-medium text-gray-800">{formatFileSize(imageFileSize)}</span>
                </span>
              {/if}
            </div>

            <!-- Smaller download button -->
            <Button
              variant="primary"
              size="sm"
              onclick={downloadImage}
              class="!bg-blue-600 !hover:bg-blue-700 !text-white !rounded-lg !px-4 !py-2 !text-sm !font-medium gap-2 w-full sm:w-auto"
            >
              <IconDownload class="h-3.5 w-3.5" />
              Download Image
            </Button>
          </div>

          <!-- VIEW PROMPT section -->
          {#if metadata?.prompt}
            <details class="group border-t border-gray-200 mt-4 pt-3">
              <summary class="cursor-pointer select-none list-none flex items-center justify-between py-1.5 hover:bg-gray-50 -mx-2 px-2 rounded transition-colors">
                <span class="text-xs sm:text-sm font-semibold text-gray-700 uppercase tracking-wide">View Prompt</span>
                <span class="text-xs sm:text-sm text-gray-500 hover:text-gray-700 transition-colors">Click to toggle</span>
              </summary>
              <div class="mt-2 p-3 sm:p-4 bg-gray-50 rounded-lg max-h-[150px] sm:max-h-[180px] 2xl:max-h-[200px] overflow-y-auto">
                <p class="text-xs sm:text-sm text-gray-700 leading-relaxed break-words">{metadata.prompt}</p>
                <button
                  onclick={copyPrompt}
                  class="mt-3 text-xs sm:text-sm text-blue-600 hover:text-blue-700 font-medium flex items-center gap-2 transition-colors"
                >
                  {#if copiedIcon}
                    <IconCheck class="h-3.5 w-3.5 text-green-500" />
                    <span>Copied!</span>
                  {:else}
                    <IconCopy class="h-3.5 w-3.5" />
                    <span>Copy prompt</span>
                  {/if}
                </button>
              </div>
            </details>
          {/if}
        </div>
      {/if}
    </div>
  </Dialog.Content>
</Dialog.Root>

<!-- Toast notification -->
{#if downloadedToast}
  <div
    class="fixed bottom-4 right-4 bg-primary border border-default rounded-lg shadow-lg px-4 py-3 flex items-center gap-2 z-50"
    in:fly={{ y: 20, duration: 200 }}
    out:fade={{ duration: 200 }}
  >
    <IconDownload class="h-4 w-4 text-green-500" />
    <span class="text-sm">Image downloaded</span>
  </div>
{/if}