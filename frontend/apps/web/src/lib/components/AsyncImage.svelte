<script lang="ts">
  import placeholderImageUrl from "$lib/assets/GeneratedImagePlaceholder.svg";
  import { IconDownload } from "@intric/icons/download";
  import { IconLinkExternal } from "@intric/icons/link-external";
  import { Button, Dialog } from "@intric/ui";
  import { writable } from "svelte/store";

  type Props = {
    url: string | null;
    metadata?: {
      size?: string;
      prompt?: string;
      fileSize?: number;
    };
  };

  const { url, metadata }: Props = $props();

  let imageLoaded = $state(false);
  let imageError = $state(false);
  let imageDimensions = $state<{ width: number; height: number } | null>(null);
  let imageFileSize = $state<number>(0);

  const dialogOpenStore = writable(false);

  // Format file size for display
  const formatFileSize = (bytes: number) => {
    if (!bytes) return '';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
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
</script>

<Dialog.Root openController={dialogOpenStore}>
  <button
    type="button"
    class="group relative max-w-[450px] overflow-hidden rounded-xl border border-default bg-secondary cursor-pointer transition-all hover:shadow-lg hover:scale-[1.02] text-left w-full"
    onclick={() => dialogOpenStore.set(true)}
    aria-label="Click to view full size"
  >
    {#if !imageLoaded && !imageError}
      <img
        src={placeholderImageUrl}
        class="w-full h-auto animate-pulse opacity-50"
        alt="Loading"
      />
    {/if}
    {#if url}
      <img
        src={url}
        class="w-full h-auto transition-opacity duration-300 {imageLoaded ? 'opacity-100' : 'opacity-0'}"
        onload={(e) => {
          imageLoaded = true;
          imageError = false;
          const img = e.target as HTMLImageElement;
          if (img) {
            imageDimensions = { width: img.naturalWidth, height: img.naturalHeight };
          }
        }}
        onerror={() => {
          console.error('[AsyncImage] Failed to load image:', url);
          imageError = true;
          imageLoaded = false;
        }}
        alt="Generated content"
      />
      {#if imageLoaded}
        <div class="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-all duration-200">
          {#if imageDimensions}
            <div class="absolute bottom-3 left-3 text-white text-sm">
              <span class="bg-black/60 backdrop-blur-sm px-3 py-1.5 rounded-lg text-xs font-medium">
                {imageDimensions.width}×{imageDimensions.height}
              </span>
            </div>
          {/if}
          <div class="absolute top-3 right-3 bg-white/90 backdrop-blur-sm p-2 rounded-lg">
            <IconLinkExternal class="text-primary h-4 w-4" />
          </div>
        </div>
      {/if}
    {/if}

    {#if imageError}
      <div class="flex flex-col items-center justify-center p-8 text-secondary">
        <p>Failed to load image</p>
        <p class="text-xs mt-2">Please try generating again</p>
      </div>
    {/if}
  </button>

  <Dialog.Content class="rounded-2xl overflow-hidden shadow-2xl">
    <div class="flex flex-col h-full max-h-[90vh] bg-primary">
      {#if url && imageLoaded}
        <div class="flex-1 flex flex-col items-center justify-center p-6 min-h-0 bg-secondary/50">
          <img
            src={url}
            class="max-w-full max-h-full object-contain rounded-lg shadow-lg"
            alt="Full size view"
            onload={(e) => {
              const img = e.target as HTMLImageElement;
              if (img) {
                imageDimensions = { width: img.naturalWidth, height: img.naturalHeight };
              }
            }}
          />
          {#if imageDimensions || imageFileSize}
            <div class="mt-3 flex items-center gap-3 text-xs text-secondary">
              {#if imageDimensions}
                <span>{imageDimensions.width}×{imageDimensions.height}</span>
              {/if}
              {#if imageDimensions && imageFileSize}
                <span>·</span>
              {/if}
              {#if imageFileSize}
                <span>{formatFileSize(imageFileSize)}</span>
              {/if}
            </div>
          {/if}
        </div>
        <div class="border-t border-default bg-primary">
          <div class="p-5 space-y-4">
            {#if metadata?.prompt}
              <div class="bg-secondary/50 rounded-xl p-4">
                <h3 class="text-xs font-semibold text-secondary uppercase tracking-wider mb-2">Prompt</h3>
                <p class="text-sm text-primary leading-relaxed line-clamp-2">{metadata.prompt}</p>
              </div>
            {/if}
            <div class="flex items-center justify-between">
              <div class="text-sm space-y-1">
                {#if metadata?.size}
                  <div>
                    <span class="text-xs text-secondary font-medium">Requested:</span>
                    <span class="ml-2 font-medium">{metadata.size}</span>
                  </div>
                {/if}
                {#if imageDimensions}
                  <div>
                    <span class="text-xs text-secondary font-medium">Actual:</span>
                    <span class="ml-2 font-medium">{imageDimensions.width}×{imageDimensions.height}</span>
                  </div>
                {/if}
              </div>
              <Button
                href={url}
                download="generated-image.png"
                variant="primary"
                class="gap-2 shadow-sm"
              >
                <IconDownload class="h-4 w-4" />
                Download
              </Button>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </Dialog.Content>
</Dialog.Root>
