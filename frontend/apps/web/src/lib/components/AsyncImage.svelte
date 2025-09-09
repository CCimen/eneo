<script lang="ts">
  import placeholderImageUrl from "$lib/assets/GeneratedImagePlaceholder.svg";
  import { IconDownload } from "@intric/icons/download";
  import { Button } from "@intric/ui";

  type Props = {
    url: string | null;
    fixedAspectRatio?: false | string;
  };

  const { url, fixedAspectRatio = "800 / 608" }: Props = $props();
  
  let imageLoaded = $state(false);
  
  // Debug logging - use $effect for reactive logging
  $effect(() => {
    console.log('[AsyncImage Debug] Component initialized with URL:', url);
    console.log('[AsyncImage Debug] imageLoaded state:', imageLoaded);
  });
</script>

<div
  class="group relative overflow-clip rounded-lg"
  style={fixedAspectRatio ? `aspect-ratio: ${fixedAspectRatio};` : undefined}
>
  <img
    src={placeholderImageUrl}
    class="bg-secondary absolute m-0 animate-pulse p-0 {imageLoaded ? 'hidden' : ''}"
    alt="placeholder"
    onload={() => console.log('[AsyncImage Debug] Placeholder loaded')}
  />
  {#if url}
    <!-- Add debugging info -->
    {#if !imageLoaded}
      <div class="absolute top-4 left-4 bg-black bg-opacity-50 text-white p-2 text-xs z-10">
        Loading: {url.slice(-20)}...
      </div>
    {/if}
    
    <img
      src={url}
      class="relative m-0 p-0 transition-opacity duration-200"
      style="opacity: 0; "
      onload={(ev) => {
        console.log('[AsyncImage Debug] Real image onload event fired');
        console.log('[AsyncImage Debug] URL:', url);
        console.log('[AsyncImage Debug] imageLoaded before:', imageLoaded);
        
        const target = ev.target as HTMLImageElement;
        if (target) {
          console.log('[AsyncImage Debug] Setting opacity to 1');
          target.style.opacity = "1";
          imageLoaded = true;
          console.log('[AsyncImage Debug] imageLoaded after:', imageLoaded);
          console.log('[AsyncImage Debug] Should hide placeholder now');
        }
      }}
      onerror={(ev) => {
        console.error('[AsyncImage Debug] Image failed to load:', url);
        console.error('[AsyncImage Debug] Error event:', ev);
        console.error('[AsyncImage Debug] imageLoaded state:', imageLoaded);
      }}
      alt="The generated file"
    />
    <Button
      href={url}
      unstyled
      variant="outlined"
      class="border-stronger bg-secondary hover:bg-tertiary absolute top-2 right-2 hidden gap-1 rounded-md border px-2 py-1 no-underline shadow group-hover:flex"
      ><IconDownload></IconDownload>Download</Button
    >
  {/if}
</div>
