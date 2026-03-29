<script lang="ts">
  import { listProjects, getFileTree } from "./lib/api";
  import type { Project } from "./lib/api";
  import CodeViewer from "./lib/CodeViewer.svelte";
  import FileTree from "./lib/FileTree.svelte";
  import QueryPanel from "./lib/QueryPanel.svelte";

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

  function handleProjectChange(e: Event) {
    const select = e.target as HTMLSelectElement;
    const project = projects.find((p) => p.id === Number(select.value));
    if (project) selectProject(project);
  }

  import { onMount } from "svelte";

  onMount(() => {
    loadProjects();
  });
</script>

<header>
  <h1>CodeSherpa</h1>
  <div class="project-selector">
    {#if loadingProjects}
      <span class="loading-text">Loading projects...</span>
    {:else if projects.length === 0}
      <span class="loading-text">No projects found. Ingest a codebase first.</span>
    {:else}
      <label for="project-select">Project:</label>
      <select id="project-select" onchange={handleProjectChange}>
        {#each projects as project}
          <option value={project.id} selected={selectedProject?.id === project.id}>
            {project.name}
            ({project.file_count} files, {project.chunk_count} chunks)
          </option>
        {/each}
      </select>
    {/if}
  </div>
</header>

<main>
  {#if selectedProject}
    <aside>
      {#if loadingFiles}
        <div class="loading-text">Loading file tree...</div>
      {:else}
        <FileTree {files} {selectedFile} onselect={handleFileSelect} />
      {/if}
    </aside>
    <section class="content">
      {#if selectedFile}
        <CodeViewer projectId={selectedProject.id} filePath={selectedFile} />
      {/if}
      <QueryPanel projectId={selectedProject.id} />
    </section>
  {/if}
</main>

<style>
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border);
  }

  h1 {
    font-size: 1.2rem;
    color: var(--accent);
  }

  .project-selector {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  label {
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  select {
    background: var(--bg-input);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 0.9rem;
  }

  main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  aside {
    width: 280px;
    min-width: 280px;
    padding: 16px;
    border-right: 1px solid var(--border);
    overflow-y: auto;
  }

  .content {
    flex: 1;
    padding: 16px 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .loading-text {
    color: var(--text-muted);
    font-size: 0.9rem;
  }
</style>
