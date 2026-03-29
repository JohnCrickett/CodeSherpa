<script lang="ts">
  import { onMount } from "svelte";
  import {
    listProjects,
    createProject,
    deleteProject,
    startIngestion,
  } from "./api";
  import type { Project, IngestionEvent } from "./api";
  import { Button } from "$lib/components/ui/button";
  import * as Card from "$lib/components/ui/card";

  interface Props {
    onNavigateToExplorer: (project: Project) => void;
  }

  let { onNavigateToExplorer }: Props = $props();

  let projects: Project[] = $state([]);
  let loading = $state(true);

  // Create form state
  let formName = $state("");
  let formSource = $state("");
  let formError = $state("");
  let formSubmitting = $state(false);

  // Delete confirmation state
  let confirmingDeleteId: number | null = $state(null);
  let deleting = $state(false);
  let deleteError = $state("");

  // Ingestion state per project id
  let ingestionState: Record<
    number,
    {
      active: boolean;
      phase: string;
      batch?: number;
      totalBatches?: number;
      current?: number;
      total?: number;
      totalFiles?: number;
      totalChunks?: number;
      chunksDone?: number;
      chunksTotal?: number;
      error?: string;
      stats?: IngestionEvent["stats"];
    }
  > = $state({});

  let loadError = $state("");

  async function loadProjects() {
    loading = true;
    loadError = "";
    try {
      projects = await listProjects();
    } catch (err) {
      loadError = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  async function handleCreate(e: SubmitEvent) {
    e.preventDefault();
    formError = "";

    const name = formName.trim();
    const source = formSource.trim();

    if (!name) {
      formError = "Project name is required.";
      return;
    }
    if (!source) {
      formError = "Source path is required.";
      return;
    }

    formSubmitting = true;
    try {
      await createProject(name, source);
      formName = "";
      formSource = "";
      await loadProjects();
    } catch (err) {
      formError = err instanceof Error ? err.message : String(err);
    } finally {
      formSubmitting = false;
    }
  }

  function handleDeleteClick(project: Project) {
    confirmingDeleteId = project.id;
    deleteError = "";
  }

  function cancelDelete() {
    confirmingDeleteId = null;
    deleteError = "";
  }

  async function confirmDelete(project: Project) {
    deleting = true;
    deleteError = "";
    try {
      await deleteProject(project.id);
      confirmingDeleteId = null;
      delete ingestionState[project.id];
      await loadProjects();
    } catch (err) {
      deleteError = err instanceof Error ? err.message : String(err);
    } finally {
      deleting = false;
    }
  }

  function handleIngest(project: Project) {
    ingestionState[project.id] = { active: true, phase: "starting" };

    startIngestion(
      project.id,
      (event: IngestionEvent) => {
        if (event.phase === "complete") {
          ingestionState[project.id] = {
            active: false,
            phase: "complete",
            stats: event.stats,
          };
          loadProjects();
        } else if (event.phase === "error") {
          ingestionState[project.id] = {
            active: false,
            phase: "error",
            error: event.message ?? "Unknown error",
          };
        } else if (event.phase === "retrying") {
          ingestionState[project.id] = {
            active: true,
            phase: "retrying",
            error: event.message,
          };
        } else {
          ingestionState[project.id] = {
            active: true,
            phase: event.phase,
            batch: event.batch,
            totalBatches: event.total_batches,
            current: event.current,
            total: event.total,
            totalFiles: event.total_files ?? ingestionState[project.id]?.totalFiles,
            totalChunks: event.total_chunks ?? ingestionState[project.id]?.totalChunks,
            chunksDone: event.chunks_done,
            chunksTotal: event.chunks_total,
          };
        }
      },
      (error: string) => {
        ingestionState[project.id] = {
          active: false,
          phase: "error",
          error,
        };
      },
    );
  }

  function progressText(state: (typeof ingestionState)[number]): string {
    if (state.phase === "parsing") {
      const files = state.totalFiles != null ? `${state.totalFiles} files` : "files";
      return `Parsing ${files}...`;
    }
    if (state.phase === "parsing_done") {
      return `Found ${state.totalChunks ?? "?"} chunks in ${state.totalFiles ?? "?"} files. Checking for changes...`;
    }
    if (state.phase === "embedding") {
      const done = state.chunksDone ?? 0;
      const total = state.chunksTotal ?? 0;
      return `Embedding chunks: ${done}/${total} (batch ${state.batch ?? "?"}/${state.totalBatches ?? "?"})`;
    }
    if (state.phase === "storing") {
      const done = state.chunksDone ?? 0;
      const total = state.chunksTotal ?? 0;
      return `Storing chunks: ${done}/${total} (file ${state.current ?? "?"}/${state.total ?? "?"})`;
    }
    if (state.phase === "starting") return "Starting ingestion...";
    if (state.phase === "retrying") return state.error ?? "Retrying...";
    return state.phase;
  }

  function progressPercent(state: (typeof ingestionState)[number]): number | null {
    if (state.phase === "embedding" && state.chunksDone != null && state.chunksTotal != null && state.chunksTotal > 0) {
      return Math.round((state.chunksDone / state.chunksTotal) * 100);
    }
    if (state.phase === "storing" && state.chunksDone != null && state.chunksTotal != null && state.chunksTotal > 0) {
      return Math.round((state.chunksDone / state.chunksTotal) * 100);
    }
    return null;
  }

  onMount(() => {
    loadProjects();
  });
</script>

<div class="mx-auto max-w-4xl space-y-6 p-6">
  <h1 class="text-xl font-semibold">Projects</h1>

  <!-- Create Project Form -->
  <Card.Root>
    <Card.Header>
      <Card.Title>Create Project</Card.Title>
    </Card.Header>
    <Card.Content>
      <form onsubmit={handleCreate} class="space-y-3">
        <div class="flex gap-3">
          <input
            type="text"
            bind:value={formName}
            placeholder="Project name"
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <input
            type="text"
            bind:value={formSource}
            placeholder="Local path or GitHub URL"
            class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          />
          <Button type="submit" class="h-9 shrink-0" disabled={formSubmitting}>
            {formSubmitting ? "Creating..." : "Create"}
          </Button>
        </div>
        {#if formError}
          <p class="text-sm text-red-500">{formError}</p>
        {/if}
      </form>
    </Card.Content>
  </Card.Root>

  <!-- Project List -->
  {#if loading}
    <p class="text-sm text-muted-foreground">Loading projects...</p>
  {:else if loadError}
    <p class="text-sm text-red-500">Failed to load projects: {loadError}</p>
  {:else if projects.length === 0}
    <p class="text-sm text-muted-foreground">No projects yet. Create one above.</p>
  {:else}
    <div class="space-y-3">
      {#each projects as project (project.id)}
        {@const istate = ingestionState[project.id]}
        {@const isIngesting = istate?.active ?? false}
        {@const isConfirmingDelete = confirmingDeleteId === project.id}
        <Card.Root>
          <Card.Content class="flex items-start justify-between gap-4 pt-6">
            <div class="min-w-0 flex-1">
              <h3 class="text-sm font-medium">{project.name}</h3>
              <p class="truncate text-xs text-muted-foreground">{project.source_path}</p>
              <div class="mt-1 flex gap-4 text-xs text-muted-foreground">
                <span>{project.file_count} files</span>
                <span>{project.chunk_count} chunks</span>
                {#if project.last_ingested_at}
                  <span>Last ingested: {new Date(project.last_ingested_at).toLocaleString()}</span>
                {:else}
                  <span>Not yet ingested</span>
                {/if}
              </div>

              <!-- Delete confirmation -->
              {#if isConfirmingDelete}
                <div class="mt-3 rounded-md border border-red-300 bg-red-50 p-3 text-xs dark:border-red-800 dark:bg-red-950">
                  <p class="font-medium text-red-700 dark:text-red-400">
                    Delete "{project.name}"? This will remove all code chunks, memory, and project data permanently.
                  </p>
                  <div class="mt-2 flex gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={deleting}
                      onclick={() => confirmDelete(project)}
                    >
                      {deleting ? "Deleting..." : "Yes, delete"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={deleting}
                      onclick={cancelDelete}
                    >
                      Cancel
                    </Button>
                  </div>
                  {#if deleteError}
                    <p class="mt-2 text-red-500">{deleteError}</p>
                  {/if}
                </div>
              {/if}

              <!-- Ingestion progress / result area -->
              {#if istate}
                <div class="mt-3">
                  {#if istate.active}
                    <div class="space-y-1">
                      <p class="text-xs font-medium">{progressText(istate)}</p>
                      {#if progressPercent(istate) != null}
                        <div class="h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            class="h-full rounded-full bg-primary transition-all"
                            style="width: {progressPercent(istate)}%"
                          ></div>
                        </div>
                      {/if}
                    </div>
                  {:else if istate.phase === "complete" && istate.stats}
                    <div class="rounded-md border bg-muted/50 p-3 text-xs">
                      <p class="font-medium">Ingestion complete</p>
                      <div class="mt-1 flex gap-4 text-muted-foreground">
                        <span>{istate.stats.chunks_stored} chunks stored</span>
                        <span>{istate.stats.files_skipped} files skipped</span>
                        <span>{istate.stats.files_updated} files updated</span>
                        <span>{istate.stats.files_deleted} files removed</span>
                      </div>
                    </div>
                  {:else if istate.phase === "error"}
                    <p class="text-xs text-red-500">{istate.error}</p>
                  {/if}
                </div>
              {/if}
            </div>

            <div class="flex shrink-0 gap-2">
              {#if project.last_ingested_at}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isIngesting}
                  onclick={() => handleIngest(project)}
                >
                  {isIngesting ? "Ingesting..." : "Re-ingest"}
                </Button>
              {:else}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={isIngesting}
                  onclick={() => handleIngest(project)}
                >
                  {isIngesting ? "Ingesting..." : "Ingest"}
                </Button>
              {/if}
              <Button
                size="sm"
                onclick={() => onNavigateToExplorer(project)}
              >
                Explore
              </Button>
              <Button
                variant="outline"
                size="sm"
                class="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                disabled={isIngesting}
                onclick={() => handleDeleteClick(project)}
              >
                Delete
              </Button>
            </div>
          </Card.Content>
        </Card.Root>
      {/each}
    </div>
  {/if}
</div>
