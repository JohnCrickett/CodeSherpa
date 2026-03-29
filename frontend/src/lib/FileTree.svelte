<script lang="ts">
  import { cn } from "$lib/utils";

  interface Props {
    files: string[];
    selectedFile?: string | null;
    onselect?: (path: string) => void;
  }

  let { files, selectedFile = null, onselect }: Props = $props();

  interface TreeNode {
    name: string;
    children: Map<string, TreeNode>;
    isFile: boolean;
  }

  function buildTree(paths: string[]): TreeNode {
    const root: TreeNode = { name: "", children: new Map(), isFile: false };
    for (const path of paths) {
      const parts = path.split("/");
      let node = root;
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        if (!node.children.has(part)) {
          node.children.set(part, {
            name: part,
            children: new Map(),
            isFile: i === parts.length - 1,
          });
        }
        node = node.children.get(part)!;
      }
    }
    return root;
  }

  let tree = $derived(buildTree(files));
  let expanded: Record<string, boolean> = $state({});

  function toggle(path: string) {
    expanded[path] = !expanded[path];
  }

  function getEntries(node: TreeNode): [string, TreeNode][] {
    return [...node.children.entries()].sort((a, b) => {
      if (a[1].isFile !== b[1].isFile) return a[1].isFile ? 1 : -1;
      return a[0].localeCompare(b[0]);
    });
  }
</script>

{#snippet renderNode(node: TreeNode, path: string, depth: number)}
  {#each getEntries(node) as [name, child]}
    {@const fullPath = path ? `${path}/${name}` : name}
    {#if child.isFile}
      <button
        class={cn(
          "flex w-full items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-left text-xs transition-colors hover:bg-accent hover:text-accent-foreground",
          selectedFile === fullPath && "bg-accent text-accent-foreground"
        )}
        style="padding-left: {depth * 12 + 6}px"
        onclick={() => onselect?.(fullPath)}
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5 shrink-0 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>
        <span class="truncate">{name}</span>
      </button>
    {:else}
      <button
        class="flex w-full items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-left text-xs font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
        style="padding-left: {depth * 12 + 6}px"
        onclick={() => toggle(fullPath)}
      >
        {#if expanded[fullPath]}
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 shrink-0 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
        {:else}
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 shrink-0 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>
        {/if}
        <span class="truncate">{name}</span>
      </button>
      {#if expanded[fullPath]}
        {@render renderNode(child, fullPath, depth + 1)}
      {/if}
    {/if}
  {/each}
{/snippet}

<div>
  <h3 class="mb-1 px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Files</h3>
  {#if files.length === 0}
    <p class="px-2 text-xs text-muted-foreground">No files indexed.</p>
  {:else}
    {@render renderNode(tree, "", 0)}
  {/if}
</div>
