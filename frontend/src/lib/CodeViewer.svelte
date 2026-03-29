<script lang="ts">
  import { getFileContent } from "./api";
  import type { FileChunk } from "./api";
  import { highlight, langFromPath } from "./highlight";
  import * as Card from "$lib/components/ui/card";

  interface Props {
    projectId: number;
    filePath: string;
    dark?: boolean;
  }

  let { projectId, filePath, dark = true }: Props = $props();

  let chunks: FileChunk[] = $state([]);
  let loading = $state(false);
  let error: string | null = $state(null);
  let highlightedHtml: string = $state("");

  let fullText = $derived(
    chunks
      .toSorted((a, b) => a.start_char - b.start_char)
      .map((c) => c.code_text)
      .join("\n")
  );

  async function load(pid: number, fp: string) {
    loading = true;
    error = null;
    highlightedHtml = "";
    try {
      chunks = await getFileContent(pid, fp);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load file.";
      chunks = [];
    } finally {
      loading = false;
    }
  }

  async function doHighlight(code: string, fp: string, isDark: boolean) {
    if (!code) return;
    const lang = langFromPath(fp);
    highlightedHtml = await highlight(code, lang, isDark);
  }

  $effect(() => {
    load(projectId, filePath);
  });

  $effect(() => {
    if (fullText) {
      doHighlight(fullText, filePath, dark);
    }
  });
</script>

<Card.Root>
  <Card.Header class="px-4 py-2">
    <Card.Title class="font-mono text-xs font-medium">{filePath}</Card.Title>
  </Card.Header>
  <Card.Content class="p-0">
    {#if loading}
      <div class="px-4 py-3 text-xs text-muted-foreground">Loading...</div>
    {:else if error}
      <div class="px-4 py-3 text-xs text-destructive">{error}</div>
    {:else if chunks.length === 0}
      <div class="px-4 py-3 text-xs text-muted-foreground">No content found.</div>
    {:else if highlightedHtml}
      <div class="shiki-wrapper max-h-[60vh] overflow-auto border-t">
        {@html highlightedHtml}
      </div>
    {:else}
      <pre class="max-h-[60vh] overflow-auto border-t bg-muted/30 p-3 text-[11px] leading-relaxed"><code class="font-mono">{fullText}</code></pre>
    {/if}
  </Card.Content>
</Card.Root>

<style>
  .shiki-wrapper :global(pre) {
    margin: 0;
    padding: 0.75rem;
    font-size: 11px;
    line-height: 1.6;
    border-radius: 0;
    background: transparent !important;
  }

  .shiki-wrapper :global(code) {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", "Fira Code", "Cascadia Code", Menlo, monospace;
  }
</style>
