<script lang="ts">
  import { highlight, langFromPath } from "./highlight";

  interface Props {
    code: string;
    filePath: string;
    dark?: boolean;
  }

  let { code, filePath, dark = true }: Props = $props();

  let html: string = $state("");

  async function doHighlight(c: string, fp: string, isDark: boolean) {
    const lang = langFromPath(fp);
    html = await highlight(c, lang, isDark);
  }

  $effect(() => {
    doHighlight(code, filePath, dark);
  });
</script>

{#if html}
  <div class="shiki-inline overflow-x-auto rounded-md border">
    {@html html}
  </div>
{:else}
  <pre class="overflow-x-auto rounded-md border bg-muted/50 p-2 text-[11px] leading-relaxed"><code>{code}</code></pre>
{/if}

<style>
  .shiki-inline :global(pre) {
    margin: 0;
    padding: 0.5rem;
    font-size: 11px;
    line-height: 1.6;
    background: transparent !important;
  }

  .shiki-inline :global(code) {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", "Fira Code", "Cascadia Code", Menlo, monospace;
  }
</style>
