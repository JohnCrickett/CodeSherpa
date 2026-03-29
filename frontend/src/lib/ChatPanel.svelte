<script lang="ts">
  import { marked } from "marked";
  import { tick } from "svelte";
  import { ask } from "./api";
  import type { Source, ConversationEntry, AskProgressEvent } from "./api";
  import { Button } from "$lib/components/ui/button";
  import { Textarea } from "$lib/components/ui/textarea";
  import { ScrollArea } from "$lib/components/ui/scroll-area";
  import HighlightedCode from "./HighlightedCode.svelte";

  function renderMarkdown(text: string): string {
    return marked.parse(text, { async: false }) as string;
  }

  interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    sources?: Source[];
    error?: boolean;
  }

  interface Props {
    projectId: number;
    dark?: boolean;
    activeFile?: string | null;
    onFileSelect?: (path: string) => void;
  }

  let { projectId, dark = true, activeFile = null, onFileSelect }: Props = $props();

  let messages: ChatMessage[] = $state([]);
  let conversationHistory: ConversationEntry[] = $state([]);
  let followUpMode = $state(true);
  let loading = $state(false);
  let progressStatus = $state("");
  let elapsedSeconds = $state(0);
  let timerInterval: ReturnType<typeof setInterval> | null = $state(null);
  let question = $state("");

  function startTimer() {
    elapsedSeconds = 0;
    timerInterval = setInterval(() => { elapsedSeconds++; }, 1000);
  }

  function stopTimer() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }
  let messagesEnd: HTMLDivElement | undefined = $state();
  let expandedSources: Record<string, boolean> = $state({});

  function toggleSource(key: string) {
    expandedSources[key] = !expandedSources[key];
  }

  async function scrollToBottom() {
    await tick();
    messagesEnd?.scrollIntoView({ behavior: "smooth" });
  }

  function newChat() {
    messages = [];
    conversationHistory = [];
    question = "";
    loading = false;
    progressStatus = "";
    stopTimer();
    expandedSources = {};
  }

  // Reset chat when project changes
  let prevProjectId = $state(projectId);
  $effect(() => {
    if (projectId !== prevProjectId) {
      prevProjectId = projectId;
      newChat();
    }
  });

  async function handleSubmit() {
    const q = question.trim();
    if (!q || loading) return;

    const userMessage: ChatMessage = { role: "user", content: q };
    messages = [...messages, userMessage];
    question = "";
    loading = true;
    startTimer();
    scrollToBottom();

    try {
      const history = followUpMode ? conversationHistory : [];
      progressStatus = "Starting...";
      const result = await ask(projectId, q, activeFile, history, (event: AskProgressEvent) => {
        progressStatus = event.detail
          ? `${event.step} ${event.detail}`
          : event.step;
        scrollToBottom();
      });

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: result.explanation,
        sources: result.sources,
      };
      messages = [...messages, assistantMessage];

      // Append to conversation history
      const summary = result.explanation.length > 200
        ? result.explanation.slice(0, 200)
        : result.explanation;
      const files = [...new Set(result.sources.map((s) => s.file_path))];
      conversationHistory = [...conversationHistory, { query: q, summary, files }];
    } catch (e) {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content: e instanceof Error ? e.message : "An error occurred.",
        error: true,
      };
      messages = [...messages, errorMessage];
    } finally {
      loading = false;
      progressStatus = "";
      stopTimer();
      scrollToBottom();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function handleSourceClick(filePath: string) {
    onFileSelect?.(filePath);
  }
</script>

<div class="flex h-full flex-col">
  <!-- Header -->
  <div class="flex h-10 shrink-0 items-center justify-between border-b px-4">
    <span class="text-xs font-medium text-muted-foreground">Chat</span>
    <Button variant="ghost" size="sm" class="h-6 text-xs" onclick={newChat}>
      New Chat
    </Button>
  </div>

  <!-- Messages -->
  <div class="flex-1 overflow-y-auto">
    <div class="mx-auto max-w-3xl px-4 py-4">
      {#if messages.length === 0}
        <div class="flex h-full items-center justify-center pt-20">
          <p class="text-sm text-muted-foreground">Ask a question about this codebase to get started.</p>
        </div>
      {/if}

      {#each messages as message, i}
        <div class="mb-4">
          <!-- Label -->
          <div class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {message.role === "user" ? "You" : "Assistant"}
          </div>

          {#if message.role === "user"}
            <div class="rounded-lg border bg-muted/50 px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap">
              {message.content}
            </div>
          {:else if message.error}
            <div class="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {message.content}
            </div>
          {:else}
            <div class="rounded-lg border px-3 py-2">
              <div class="prose-explanation text-xs leading-relaxed">
                {@html renderMarkdown(message.content)}
              </div>

              {#if message.sources && message.sources.length > 0}
                <div class="mt-3 border-t pt-2">
                  <h4 class="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Sources</h4>
                  {#each message.sources as source, j}
                    {@const sourceKey = `${i}-${j}`}
                    <div class="mb-1.5 last:mb-0">
                      <div class="flex items-center gap-1 text-xs">
                        <span class="text-muted-foreground">[{j + 1}]</span>
                        <button
                          class="font-medium text-primary hover:underline cursor-pointer"
                          onclick={() => handleSourceClick(source.file_path)}
                        >
                          {source.file_path}
                        </button>
                        <span class="text-muted-foreground text-[10px]">
                          {source.chunk_type} · {source.start_char}-{source.end_char}
                        </span>
                        <button
                          class="ml-auto text-[10px] text-muted-foreground hover:text-foreground cursor-pointer"
                          onclick={() => toggleSource(sourceKey)}
                        >
                          {expandedSources[sourceKey] ? "Hide" : "Show"} code
                        </button>
                      </div>
                      {#if expandedSources[sourceKey]}
                        <div class="mt-1">
                          <HighlightedCode code={source.code_text} filePath={source.file_path} {dark} />
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}

      {#if loading}
        <div class="mb-4">
          <div class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Assistant
          </div>
          <div class="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs text-muted-foreground">
            <div class="h-3 w-3 animate-spin rounded-full border-[1.5px] border-muted-foreground border-t-transparent"></div>
            <span>{progressStatus || "Starting..."}</span>
            <span class="ml-auto tabular-nums">{elapsedSeconds}s</span>
          </div>
        </div>
      {/if}

      <div bind:this={messagesEnd}></div>
    </div>
  </div>

  <!-- Input area -->
  <div class="shrink-0 border-t px-4 py-3">
    <div class="mx-auto max-w-3xl">
      <form class="flex gap-2" onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
        <Textarea
          bind:value={question}
          onkeydown={handleKeydown}
          placeholder="Ask a question about this codebase..."
          rows={1}
          disabled={loading}
          class="min-h-[32px] resize-none text-xs"
        />
        <Button type="submit" size="sm" disabled={loading || !question.trim()} class="h-8 self-end text-xs">
          Ask
        </Button>
      </form>
      <div class="mt-1.5 flex items-center gap-2">
        <button
          class="flex items-center gap-1 text-[10px] cursor-pointer {followUpMode ? 'text-primary' : 'text-muted-foreground'}"
          onclick={() => followUpMode = !followUpMode}
        >
          <span class="inline-flex h-3 w-5 items-center rounded-full border transition-colors {followUpMode ? 'bg-primary' : 'bg-muted'}">
            <span class="h-2 w-2 rounded-full bg-white transition-transform {followUpMode ? 'translate-x-2.5' : 'translate-x-0.5'}"></span>
          </span>
          Follow-up mode
        </button>
        {#if conversationHistory.length > 0}
          <span class="text-[10px] text-muted-foreground">
            · {conversationHistory.length} message{conversationHistory.length === 1 ? "" : "s"} in context
          </span>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .prose-explanation :global(h1),
  .prose-explanation :global(h2),
  .prose-explanation :global(h3),
  .prose-explanation :global(h4) {
    font-weight: 600;
    margin-top: 1em;
    margin-bottom: 0.5em;
  }

  .prose-explanation :global(h1) { font-size: 1.15em; }
  .prose-explanation :global(h2) { font-size: 1.05em; }
  .prose-explanation :global(h3) { font-size: 1em; }

  .prose-explanation :global(p) {
    margin-bottom: 0.6em;
  }

  .prose-explanation :global(ul),
  .prose-explanation :global(ol) {
    padding-left: 1.5em;
    margin-bottom: 0.6em;
  }

  .prose-explanation :global(li) {
    margin-bottom: 0.25em;
  }

  .prose-explanation :global(code) {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", "Fira Code", Menlo, monospace;
    font-size: 0.9em;
    padding: 0.15em 0.35em;
    border-radius: 0.25em;
    background: var(--muted);
  }

  .prose-explanation :global(pre) {
    margin-bottom: 0.6em;
    padding: 0.6em;
    border-radius: 0.375em;
    overflow-x: auto;
    background: var(--muted);
    font-size: 11px;
    line-height: 1.6;
  }

  .prose-explanation :global(pre code) {
    padding: 0;
    background: none;
  }

  .prose-explanation :global(strong) {
    font-weight: 600;
  }

  .prose-explanation :global(blockquote) {
    border-left: 2px solid var(--border);
    padding-left: 0.75em;
    color: var(--muted-foreground);
    margin-bottom: 0.6em;
  }
</style>
