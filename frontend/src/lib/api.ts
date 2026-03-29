export interface Project {
  id: number;
  name: string;
  source_path: string;
  created_at: string | null;
  last_ingested_at: string | null;
  file_count: number;
  chunk_count: number;
}

export interface Source {
  code_text: string;
  file_path: string;
  chunk_type: string;
  language: string;
  start_char: number;
  end_char: number;
  score: number;
}

export interface ConversationEntry {
  query: string;
  summary: string;
  files: string[];
}

export interface AskResponse {
  explanation: string;
  sources: Source[];
  dependencies?: string[];
}

export interface AskProgressEvent {
  step: string;
  detail?: string;
}

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export function listProjects(): Promise<Project[]> {
  return fetchJSON<Project[]>(`${BASE}/projects`);
}

export function getFileTree(projectId: number): Promise<string[]> {
  return fetchJSON<string[]>(`${BASE}/projects/${projectId}/files`);
}

export async function ask(
  projectId: number,
  question: string,
  activeFile?: string | null,
  conversationHistory?: ConversationEntry[],
  onProgress?: (event: AskProgressEvent) => void,
): Promise<AskResponse> {
  const body: Record<string, unknown> = { question };
  if (activeFile) body.active_file = activeFile;
  if (conversationHistory && conversationHistory.length > 0) {
    body.conversation_history = conversationHistory;
  }

  const resp = await fetch(`${BASE}/projects/${projectId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
  }

  const reader = resp.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let result: AskResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const event = JSON.parse(line.slice(6));
      if (event.phase === "done") {
        result = {
          explanation: event.explanation,
          sources: event.sources,
          dependencies: event.dependencies,
        };
      } else if (event.step && onProgress) {
        onProgress(event as AskProgressEvent);
      }
    }
  }

  if (!result) throw new Error("No response received from server");
  return result;
}

export interface FileChunk {
  code_text: string;
  chunk_type: string;
  language: string;
  start_char: number;
  end_char: number;
}

export function getFileContent(projectId: number, filePath: string): Promise<FileChunk[]> {
  return fetchJSON<FileChunk[]>(`${BASE}/projects/${projectId}/files/${filePath}`);
}

export function query(projectId: number, question: string): Promise<Source[]> {
  return fetchJSON<Source[]>(`${BASE}/projects/${projectId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export interface CreateProjectResponse {
  id: number;
  name: string;
  source_path: string;
}

export interface ApiError {
  detail: string;
}

export async function createProject(
  name: string,
  source: string,
): Promise<CreateProjectResponse> {
  const resp = await fetch(`${BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, source }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    try {
      const err: ApiError = JSON.parse(text);
      throw new Error(err.detail);
    } catch (e) {
      if (e instanceof SyntaxError) {
        throw new Error(text || `HTTP ${resp.status}: ${resp.statusText}`);
      }
      throw e;
    }
  }
  return resp.json() as Promise<CreateProjectResponse>;
}

export async function deleteProject(projectId: number): Promise<void> {
  const resp = await fetch(`${BASE}/projects/${projectId}`, {
    method: "DELETE",
  });
  if (!resp.ok) {
    const text = await resp.text();
    try {
      const err: ApiError = JSON.parse(text);
      throw new Error(err.detail);
    } catch (e) {
      if (e instanceof SyntaxError) {
        throw new Error(text || `HTTP ${resp.status}: ${resp.statusText}`);
      }
      throw e;
    }
  }
}

// --- Memory types ---

export interface EpisodicMemory {
  id: number;
  query: string;
  file_paths: string[];
  summary: string;
  created_at: string | null;
}

export interface SemanticMemory {
  id: number;
  content: string;
  created_at: string | null;
}

export interface MemorySearchResult {
  type: "episodic" | "semantic";
  id: number;
  score: number;
  query?: string;
  file_paths?: string[];
  summary?: string;
  created_at?: string | null;
  content?: string;
}

export interface BulkDeleteResult {
  deleted: number;
}

export interface BulkDeleteAllResult {
  episodic_deleted: number;
  semantic_deleted: number;
}

// --- Ingestion types ---

export interface IngestionEvent {
  phase: string;
  batch?: number;
  total_batches?: number;
  current?: number;
  total?: number;
  total_files?: number;
  total_chunks?: number;
  chunks_done?: number;
  chunks_total?: number;
  message?: string;
  stats?: {
    chunks_stored: number;
    files_skipped: number;
    files_updated: number;
    files_deleted: number;
  };
}

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 3000, 5000];

export function startIngestion(
  projectId: number,
  onEvent: (event: IngestionEvent) => void,
  onError: (error: string) => void,
): { close: () => void } {
  let cancelled = false;
  let currentController: AbortController | null = null;

  async function readStream(resp: Response): Promise<boolean> {
    const reader = resp.body?.getReader();
    if (!reader) {
      onError("No response body");
      return false;
    }
    const decoder = new TextDecoder();
    let buffer = "";
    let receivedComplete = false;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const event: IngestionEvent = JSON.parse(line.slice(6));
          onEvent(event);
          if (event.phase === "complete" || event.phase === "error") {
            receivedComplete = true;
          }
        }
      }
    }
    return receivedComplete;
  }

  async function attempt(retryCount: number): Promise<void> {
    if (cancelled) return;

    currentController = new AbortController();
    try {
      const resp = await fetch(`${BASE}/projects/${projectId}/ingest`, {
        method: "POST",
        signal: currentController.signal,
      });

      if (!resp.ok) {
        const text = await resp.text();
        // 409 means ingestion is running (maybe from a previous retry that succeeded
        // server-side but we lost the connection) — don't retry
        if (resp.status === 409 && retryCount > 0) {
          onEvent({ phase: "error", message: "Ingestion already in progress. Please wait for it to finish." });
          return;
        }
        try {
          const err: ApiError = JSON.parse(text);
          onError(err.detail);
        } catch {
          onError(text || `HTTP ${resp.status}: ${resp.statusText}`);
        }
        return;
      }

      const completed = await readStream(resp);
      if (!completed && !cancelled) {
        throw new Error("Connection lost before ingestion completed");
      }
    } catch (err) {
      if (cancelled || (err instanceof DOMException && err.name === "AbortError")) {
        return;
      }
      if (retryCount < MAX_RETRIES) {
        const delay = RETRY_DELAYS[retryCount] ?? 5000;
        onEvent({
          phase: "retrying",
          message: `Connection lost. Retrying in ${delay / 1000}s... (attempt ${retryCount + 2}/${MAX_RETRIES + 1})`,
        });
        await new Promise((r) => setTimeout(r, delay));
        return attempt(retryCount + 1);
      }
      onError(err instanceof Error ? err.message : String(err));
    }
  }

  attempt(0);

  return {
    close: () => {
      cancelled = true;
      currentController?.abort();
    },
  };
}

// --- Memory API functions ---

async function fetchWithError<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, init);
  if (!resp.ok) {
    const text = await resp.text();
    try {
      const err: ApiError = JSON.parse(text);
      throw new Error(err.detail);
    } catch (e) {
      if (e instanceof SyntaxError) {
        throw new Error(text || `HTTP ${resp.status}: ${resp.statusText}`);
      }
      throw e;
    }
  }
  return resp.json() as Promise<T>;
}

export function listEpisodicMemories(projectId: number): Promise<EpisodicMemory[]> {
  return fetchWithError<EpisodicMemory[]>(`${BASE}/projects/${projectId}/memory/episodic`);
}

export function listSemanticMemories(projectId: number): Promise<SemanticMemory[]> {
  return fetchWithError<SemanticMemory[]>(`${BASE}/projects/${projectId}/memory/semantic`);
}

export function searchMemory(projectId: number, query: string): Promise<MemorySearchResult[]> {
  return fetchWithError<MemorySearchResult[]>(`${BASE}/projects/${projectId}/memory/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
}

export async function deleteEpisodicMemory(projectId: number, memoryId: number): Promise<void> {
  await fetchWithError(`${BASE}/projects/${projectId}/memory/episodic/${memoryId}`, {
    method: "DELETE",
  });
}

export function editSemanticMemory(
  projectId: number,
  memoryId: number,
  content: string,
): Promise<{ status: string }> {
  return fetchWithError<{ status: string }>(`${BASE}/projects/${projectId}/memory/semantic/${memoryId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export function addSemanticMemory(
  projectId: number,
  content: string,
): Promise<{ status: string }> {
  return fetchWithError<{ status: string }>(`${BASE}/projects/${projectId}/memory/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}

export async function deleteSemanticMemory(projectId: number, memoryId: number): Promise<void> {
  await fetchWithError(`${BASE}/projects/${projectId}/memory/semantic/${memoryId}`, {
    method: "DELETE",
  });
}

export function bulkDeleteEpisodicMemory(projectId: number): Promise<BulkDeleteResult> {
  return fetchWithError<BulkDeleteResult>(`${BASE}/projects/${projectId}/memory/episodic`, {
    method: "DELETE",
  });
}

export function bulkDeleteSemanticMemory(projectId: number): Promise<BulkDeleteResult> {
  return fetchWithError<BulkDeleteResult>(`${BASE}/projects/${projectId}/memory/semantic`, {
    method: "DELETE",
  });
}

export function bulkDeleteAllMemory(projectId: number): Promise<BulkDeleteAllResult> {
  return fetchWithError<BulkDeleteAllResult>(`${BASE}/projects/${projectId}/memory`, {
    method: "DELETE",
  });
}
