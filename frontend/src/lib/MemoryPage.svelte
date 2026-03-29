<script lang="ts">
  import { onMount } from "svelte";
  import {
    listProjects,
    listEpisodicMemories,
    listSemanticMemories,
    searchMemory,
    deleteEpisodicMemory,
    deleteSemanticMemory,
    addSemanticMemory,
    editSemanticMemory,
    bulkDeleteEpisodicMemory,
    bulkDeleteSemanticMemory,
    bulkDeleteAllMemory,
  } from "./api";
  import type {
    Project,
    EpisodicMemory,
    SemanticMemory,
    MemorySearchResult,
  } from "./api";
  import { Button } from "$lib/components/ui/button";
  import * as Card from "$lib/components/ui/card";
  import * as Select from "$lib/components/ui/select";
  import { Textarea } from "$lib/components/ui/textarea";

  interface Props {
    initialProjectId?: number | null;
  }

  let { initialProjectId = null }: Props = $props();

  // Project state
  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(null);
  let loadingProjects = $state(true);

  // Memory data
  let episodicMemories: EpisodicMemory[] = $state([]);
  let semanticMemories: SemanticMemory[] = $state([]);
  let loadingMemories = $state(false);
  let memoryError = $state("");

  // Search state
  let searchQuery = $state("");
  let searchResults: MemorySearchResult[] = $state([]);
  let searching = $state(false);
  let searchActive = $state(false);
  let searchError = $state("");

  // Add semantic memory form
  let addContent = $state("");
  let addError = $state("");
  let adding = $state(false);

  // Edit state
  let editingId: number | null = $state(null);
  let editContent = $state("");
  let editError = $state("");
  let saving = $state(false);

  // Delete state
  let deletingId: number | null = $state(null);
  let deleteType: "episodic" | "semantic" | null = $state(null);

  // Bulk delete confirmation
  let bulkConfirm: "episodic" | "semantic" | "all" | null = $state(null);
  let bulkDeleting = $state(false);
  let bulkError = $state("");

  async function loadProjects() {
    loadingProjects = true;
    try {
      projects = await listProjects();
      if (initialProjectId && projects.some((p) => p.id === initialProjectId)) {
        selectedProjectId = initialProjectId;
      } else if (projects.length > 0 && !selectedProjectId) {
        selectedProjectId = projects[0].id;
      }
    } finally {
      loadingProjects = false;
    }
  }

  async function loadMemories() {
    if (!selectedProjectId) return;
    loadingMemories = true;
    memoryError = "";
    try {
      const [ep, sem] = await Promise.all([
        listEpisodicMemories(selectedProjectId),
        listSemanticMemories(selectedProjectId),
      ]);
      episodicMemories = ep;
      semanticMemories = sem;
    } catch (err) {
      memoryError = err instanceof Error ? err.message : String(err);
    } finally {
      loadingMemories = false;
    }
  }

  function handleProjectChange(value: string | undefined) {
    if (!value) return;
    selectedProjectId = Number(value);
    searchQuery = "";
    searchActive = false;
    searchResults = [];
    editingId = null;
    bulkConfirm = null;
    loadMemories();
  }

  async function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    const query = searchQuery.trim();
    if (!query || !selectedProjectId) {
      searchActive = false;
      searchResults = [];
      return;
    }
    searching = true;
    searchError = "";
    try {
      searchResults = await searchMemory(selectedProjectId, query);
      searchActive = true;
    } catch (err) {
      searchError = err instanceof Error ? err.message : String(err);
    } finally {
      searching = false;
    }
  }

  function clearSearch() {
    searchQuery = "";
    searchActive = false;
    searchResults = [];
    searchError = "";
  }

  async function handleAdd(e: SubmitEvent) {
    e.preventDefault();
    const content = addContent.trim();
    if (!content || !selectedProjectId) {
      addError = "Content is required.";
      return;
    }
    adding = true;
    addError = "";
    try {
      await addSemanticMemory(selectedProjectId, content);
      addContent = "";
      await loadMemories();
    } catch (err) {
      addError = err instanceof Error ? err.message : String(err);
    } finally {
      adding = false;
    }
  }

  function startEdit(mem: SemanticMemory) {
    editingId = mem.id;
    editContent = mem.content;
    editError = "";
  }

  function cancelEdit() {
    editingId = null;
    editContent = "";
    editError = "";
  }

  async function saveEdit() {
    if (!selectedProjectId || editingId === null) return;
    const content = editContent.trim();
    if (!content) {
      editError = "Content cannot be empty.";
      return;
    }
    saving = true;
    editError = "";
    try {
      await editSemanticMemory(selectedProjectId, editingId, content);
      editingId = null;
      editContent = "";
      await loadMemories();
    } catch (err) {
      editError = err instanceof Error ? err.message : String(err);
    } finally {
      saving = false;
    }
  }

  async function handleDeleteEpisodic(id: number) {
    if (!selectedProjectId) return;
    deletingId = id;
    deleteType = "episodic";
    try {
      await deleteEpisodicMemory(selectedProjectId, id);
      if (searchActive) {
        searchResults = searchResults.filter((r) => !(r.type === "episodic" && r.id === id));
      }
      await loadMemories();
    } finally {
      deletingId = null;
      deleteType = null;
    }
  }

  async function handleDeleteSemantic(id: number) {
    if (!selectedProjectId) return;
    deletingId = id;
    deleteType = "semantic";
    try {
      await deleteSemanticMemory(selectedProjectId, id);
      if (searchActive) {
        searchResults = searchResults.filter((r) => !(r.type === "semantic" && r.id === id));
      }
      await loadMemories();
    } finally {
      deletingId = null;
      deleteType = null;
    }
  }

  async function handleBulkDelete() {
    if (!selectedProjectId || !bulkConfirm) return;
    bulkDeleting = true;
    bulkError = "";
    try {
      if (bulkConfirm === "episodic") {
        await bulkDeleteEpisodicMemory(selectedProjectId);
      } else if (bulkConfirm === "semantic") {
        await bulkDeleteSemanticMemory(selectedProjectId);
      } else {
        await bulkDeleteAllMemory(selectedProjectId);
      }
      bulkConfirm = null;
      if (searchActive) {
        searchResults = [];
        searchActive = false;
        searchQuery = "";
      }
      await loadMemories();
    } catch (err) {
      bulkError = err instanceof Error ? err.message : String(err);
    } finally {
      bulkDeleting = false;
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "";
    return new Date(dateStr).toLocaleString();
  }

  $effect(() => {
    if (selectedProjectId) {
      loadMemories();
    }
  });

  onMount(() => {
    loadProjects();
  });
</script>

<div class="mx-auto max-w-4xl space-y-6 p-6">
  <div class="flex items-center justify-between">
    <h1 class="text-xl font-semibold">Memory</h1>

    <!-- Project selector -->
    {#if loadingProjects}
      <span class="text-xs text-muted-foreground">Loading projects...</span>
    {:else if projects.length === 0}
      <span class="text-xs text-muted-foreground">No projects found.</span>
    {:else}
      <Select.Root
        type="single"
        value={selectedProjectId ? String(selectedProjectId) : undefined}
        onValueChange={handleProjectChange}
      >
        <Select.Trigger class="h-8 w-[260px] text-xs">
          {#if selectedProjectId}
            {@const proj = projects.find((p) => p.id === selectedProjectId)}
            {proj?.name ?? "Select project"}
          {:else}
            Select project
          {/if}
        </Select.Trigger>
        <Select.Content>
          {#each projects as project}
            <Select.Item value={String(project.id)} class="text-xs">
              {project.name}
            </Select.Item>
          {/each}
        </Select.Content>
      </Select.Root>
    {/if}
  </div>

  {#if !selectedProjectId}
    <p class="text-sm text-muted-foreground">Select a project to view its memory.</p>
  {:else}
    <!-- Search -->
    <Card.Root>
      <Card.Content class="pt-6">
        <form onsubmit={handleSearch} class="flex gap-3">
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="Search memory..."
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <Button type="submit" size="sm" class="h-9 shrink-0" disabled={searching}>
            {searching ? "Searching..." : "Search"}
          </Button>
          {#if searchActive}
            <Button variant="outline" size="sm" class="h-9 shrink-0" onclick={clearSearch}>
              Clear
            </Button>
          {/if}
        </form>
        {#if searchError}
          <p class="mt-2 text-sm text-red-500">{searchError}</p>
        {/if}
      </Card.Content>
    </Card.Root>

    {#if loadingMemories}
      <p class="text-sm text-muted-foreground">Loading memories...</p>
    {:else if memoryError}
      <p class="text-sm text-red-500">Failed to load memories: {memoryError}</p>
    {:else if searchActive}
      <!-- Search Results -->
      <Card.Root>
        <Card.Header>
          <Card.Title>Search Results ({searchResults.length})</Card.Title>
        </Card.Header>
        <Card.Content>
          {#if searchResults.length === 0}
            <p class="text-sm text-muted-foreground">No results found.</p>
          {:else}
            <div class="space-y-3">
              {#each searchResults as result (result.type + "-" + result.id)}
                <div class="rounded-md border p-3">
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                      <span class="inline-block rounded px-1.5 py-0.5 text-[10px] font-medium uppercase {result.type === 'episodic' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' : 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'}">
                        {result.type}
                      </span>
                      <span class="ml-2 text-xs text-muted-foreground">
                        Score: {result.score.toFixed(3)}
                      </span>
                      {#if result.type === "episodic"}
                        <p class="mt-1 text-sm font-medium">{result.query}</p>
                        {#if result.file_paths && result.file_paths.length > 0}
                          <div class="mt-1 flex flex-wrap gap-1">
                            {#each result.file_paths as fp}
                              <span class="rounded bg-muted px-1.5 py-0.5 text-[10px]">{fp}</span>
                            {/each}
                          </div>
                        {/if}
                        {#if result.summary}
                          <p class="mt-1 text-xs text-muted-foreground">{result.summary}</p>
                        {/if}
                      {:else}
                        <p class="mt-1 text-sm">{result.content}</p>
                      {/if}
                      {#if result.created_at}
                        <p class="mt-1 text-[10px] text-muted-foreground">{formatDate(result.created_at)}</p>
                      {/if}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      class="shrink-0 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                      disabled={deletingId === result.id && deleteType === result.type}
                      onclick={() => result.type === "episodic" ? handleDeleteEpisodic(result.id) : handleDeleteSemantic(result.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </Card.Content>
      </Card.Root>
    {:else}
      <!-- Default two-section view -->

      <!-- Episodic Memory -->
      <Card.Root>
        <Card.Header>
          <div class="flex items-center justify-between">
            <Card.Title>Episodic Memory ({episodicMemories.length})</Card.Title>
            {#if episodicMemories.length > 0}
              <Button
                variant="outline"
                size="sm"
                class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                onclick={() => bulkConfirm = "episodic"}
              >
                Clear All Episodic Memory
              </Button>
            {/if}
          </div>
        </Card.Header>
        <Card.Content>
          {#if bulkConfirm === "episodic"}
            <div class="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-xs dark:border-red-800 dark:bg-red-950">
              <p class="font-medium text-red-700 dark:text-red-400">
                This will permanently delete all {episodicMemories.length} episodic memory entries for this project. This action cannot be undone.
              </p>
              <div class="mt-2 flex gap-2">
                <Button variant="destructive" size="sm" disabled={bulkDeleting} onclick={handleBulkDelete}>
                  {bulkDeleting ? "Deleting..." : "Confirm"}
                </Button>
                <Button variant="outline" size="sm" disabled={bulkDeleting} onclick={() => { bulkConfirm = null; bulkError = ""; }}>
                  Cancel
                </Button>
              </div>
              {#if bulkError}
                <p class="mt-2 text-red-500">{bulkError}</p>
              {/if}
            </div>
          {/if}

          {#if episodicMemories.length === 0}
            <p class="text-sm text-muted-foreground">No episodic memories recorded yet.</p>
          {:else}
            <div class="space-y-3">
              {#each episodicMemories as mem (mem.id)}
                <div class="rounded-md border p-3">
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0 flex-1">
                      <p class="text-sm font-medium">{mem.query}</p>
                      {#if mem.file_paths.length > 0}
                        <div class="mt-1 flex flex-wrap gap-1">
                          {#each mem.file_paths as fp}
                            <span class="rounded bg-muted px-1.5 py-0.5 text-[10px]">{fp}</span>
                          {/each}
                        </div>
                      {/if}
                      {#if mem.summary}
                        <p class="mt-1 text-xs text-muted-foreground">{mem.summary}</p>
                      {/if}
                      {#if mem.created_at}
                        <p class="mt-1 text-[10px] text-muted-foreground">{formatDate(mem.created_at)}</p>
                      {/if}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      class="shrink-0 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                      disabled={deletingId === mem.id && deleteType === "episodic"}
                      onclick={() => handleDeleteEpisodic(mem.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </Card.Content>
      </Card.Root>

      <!-- Semantic Memory -->
      <Card.Root>
        <Card.Header>
          <div class="flex items-center justify-between">
            <Card.Title>Semantic Memory ({semanticMemories.length})</Card.Title>
            {#if semanticMemories.length > 0}
              <Button
                variant="outline"
                size="sm"
                class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                onclick={() => bulkConfirm = "semantic"}
              >
                Clear All Semantic Memory
              </Button>
            {/if}
          </div>
        </Card.Header>
        <Card.Content>
          {#if bulkConfirm === "semantic"}
            <div class="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-xs dark:border-red-800 dark:bg-red-950">
              <p class="font-medium text-red-700 dark:text-red-400">
                This will permanently delete all {semanticMemories.length} semantic memory entries for this project. This action cannot be undone.
              </p>
              <div class="mt-2 flex gap-2">
                <Button variant="destructive" size="sm" disabled={bulkDeleting} onclick={handleBulkDelete}>
                  {bulkDeleting ? "Deleting..." : "Confirm"}
                </Button>
                <Button variant="outline" size="sm" disabled={bulkDeleting} onclick={() => { bulkConfirm = null; bulkError = ""; }}>
                  Cancel
                </Button>
              </div>
              {#if bulkError}
                <p class="mt-2 text-red-500">{bulkError}</p>
              {/if}
            </div>
          {/if}

          <!-- Add form -->
          <form onsubmit={handleAdd} class="mb-4 flex gap-2">
            <input
              type="text"
              bind:value={addContent}
              placeholder="Add semantic memory..."
              class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            <Button type="submit" size="sm" class="h-9 shrink-0" disabled={adding}>
              {adding ? "Adding..." : "Add"}
            </Button>
          </form>
          {#if addError}
            <p class="mb-3 text-sm text-red-500">{addError}</p>
          {/if}

          {#if semanticMemories.length === 0}
            <p class="text-sm text-muted-foreground">No semantic memories added yet.</p>
          {:else}
            <div class="space-y-3">
              {#each semanticMemories as mem (mem.id)}
                <div class="rounded-md border p-3">
                  {#if editingId === mem.id}
                    <!-- Inline edit form -->
                    <div class="space-y-2">
                      <Textarea bind:value={editContent} rows={3} placeholder="Memory content..." />
                      <div class="flex gap-2">
                        <Button size="sm" disabled={saving} onclick={saveEdit}>
                          {saving ? "Saving..." : "Save"}
                        </Button>
                        <Button variant="outline" size="sm" disabled={saving} onclick={cancelEdit}>
                          Cancel
                        </Button>
                      </div>
                      {#if editError}
                        <p class="text-sm text-red-500">{editError}</p>
                      {/if}
                    </div>
                  {:else}
                    <div class="flex items-start justify-between gap-2">
                      <div class="min-w-0 flex-1">
                        <p class="text-sm">{mem.content}</p>
                        {#if mem.created_at}
                          <p class="mt-1 text-[10px] text-muted-foreground">{formatDate(mem.created_at)}</p>
                        {/if}
                      </div>
                      <div class="flex shrink-0 gap-1">
                        <Button variant="outline" size="sm" onclick={() => startEdit(mem)}>
                          Edit
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                          disabled={deletingId === mem.id && deleteType === "semantic"}
                          onclick={() => handleDeleteSemantic(mem.id)}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </Card.Content>
      </Card.Root>

      <!-- Clear All Memory -->
      {#if episodicMemories.length > 0 || semanticMemories.length > 0}
        <div class="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
            onclick={() => bulkConfirm = "all"}
          >
            Clear All Memory
          </Button>
        </div>

        {#if bulkConfirm === "all"}
          <div class="rounded-md border border-red-300 bg-red-50 p-3 text-xs dark:border-red-800 dark:bg-red-950">
            <p class="font-medium text-red-700 dark:text-red-400">
              This will permanently delete all episodic and semantic memory entries for this project. This action cannot be undone.
            </p>
            <div class="mt-2 flex gap-2">
              <Button variant="destructive" size="sm" disabled={bulkDeleting} onclick={handleBulkDelete}>
                {bulkDeleting ? "Deleting..." : "Confirm"}
              </Button>
              <Button variant="outline" size="sm" disabled={bulkDeleting} onclick={() => { bulkConfirm = null; bulkError = ""; }}>
                Cancel
              </Button>
            </div>
            {#if bulkError}
              <p class="mt-2 text-red-500">{bulkError}</p>
            {/if}
          </div>
        {/if}
      {/if}
    {/if}
  {/if}
</div>
