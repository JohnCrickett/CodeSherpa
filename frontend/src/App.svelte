<script lang="ts">
  import { onMount } from "svelte";
  import { listProjects, getFileTree } from "./lib/api";
  import type { Project } from "./lib/api";
  import CodeViewer from "./lib/CodeViewer.svelte";
  import FileTree from "./lib/FileTree.svelte";
  import QueryPanel from "./lib/QueryPanel.svelte";
  import * as Select from "$lib/components/ui/select";
  import { ScrollArea } from "$lib/components/ui/scroll-area";
  import { Button } from "$lib/components/ui/button";

  function getInitialTheme(): boolean {
    const stored = localStorage.getItem("theme");
    if (stored === "dark") return true;
    if (stored === "light") return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  let dark = $state(getInitialTheme());

  let projects: Project[] = $state([]);
  let selectedProject: Project | null = $state(null);
  let files: string[] = $state([]);
  let selectedFile: string | null = $state(null);
  let loadingProjects = $state(true);
  let loadingFiles = $state(false);

  async function loadProjects() {
    loadingProjects = true;
    try {
      projects = await listProjects();
      if (projects.length > 0 && !selectedProject) {
        await selectProject(projects[0]);
      }
    } finally {
      loadingProjects = false;
    }
  }

  async function selectProject(project: Project) {
    selectedProject = project;
    selectedFile = null;
    loadingFiles = true;
    try {
      files = await getFileTree(project.id);
    } finally {
      loadingFiles = false;
    }
  }

  function handleFileSelect(path: string) {
    selectedFile = selectedFile === path ? null : path;
  }

  function handleProjectChange(value: string | undefined) {
    if (!value) return;
    const project = projects.find((p) => String(p.id) === value);
    if (project) selectProject(project);
  }

  function toggleTheme() {
    dark = !dark;
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }

  onMount(() => {
    document.documentElement.classList.toggle("dark", dark);
    loadProjects();
  });
</script>

<div class="flex h-screen flex-col text-[13px]">
  <!-- Header -->
  <header class="flex h-10 shrink-0 items-center justify-between border-b px-4">
    <span class="text-sm font-semibold tracking-tight">CodeSherpa</span>
    <div class="flex items-center gap-2">
      {#if loadingProjects}
        <span class="text-xs text-muted-foreground">Loading...</span>
      {:else if projects.length === 0}
        <span class="text-xs text-muted-foreground">No projects found.</span>
      {:else}
        <Select.Root
          type="single"
          value={selectedProject ? String(selectedProject.id) : undefined}
          onValueChange={handleProjectChange}
        >
          <Select.Trigger class="h-7 w-[240px] text-xs">
            {#if selectedProject}
              {selectedProject.name}
              <span class="text-muted-foreground ml-1">
                {selectedProject.file_count} files
              </span>
            {:else}
              Select project
            {/if}
          </Select.Trigger>
          <Select.Content>
            {#each projects as project}
              <Select.Item value={String(project.id)} class="text-xs">
                {project.name}
                <span class="ml-auto text-muted-foreground">
                  {project.file_count} files, {project.chunk_count} chunks
                </span>
              </Select.Item>
            {/each}
          </Select.Content>
        </Select.Root>
      {/if}
      <Button variant="ghost" size="icon" class="h-7 w-7" onclick={toggleTheme} aria-label="Toggle theme">
        {#if dark}
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
        {:else}
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
        {/if}
      </Button>
    </div>
  </header>

  <!-- Main content -->
  <div class="flex flex-1 overflow-hidden">
    {#if selectedProject}
      <!-- Sidebar -->
      <aside class="w-60 min-w-60 border-r">
        <ScrollArea class="h-full">
          <div class="p-2">
            {#if loadingFiles}
              <p class="px-2 py-1 text-xs text-muted-foreground">Loading...</p>
            {:else}
              <FileTree {files} {selectedFile} onselect={handleFileSelect} />
            {/if}
          </div>
        </ScrollArea>
      </aside>

      <!-- Content area -->
      <main class="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        {#if selectedFile}
          <CodeViewer projectId={selectedProject.id} filePath={selectedFile} {dark} />
        {/if}
        <QueryPanel projectId={selectedProject.id} {dark} />
      </main>
    {/if}
  </div>
</div>
