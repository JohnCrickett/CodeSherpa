# Task 12: ChatGPT-Style Conversation UI

## Objective
Replace the single-shot QueryPanel with a ChatGPT-style conversation interface that supports ongoing dialogue, follow-up questions, and clickable source references.

## Requirements Covered
- REQ-CHAT-01: Chat is the main focus of the explorer page
- REQ-CHAT-02: ChatGPT-style message bubbles (user / assistant)
- REQ-CHAT-03: Ongoing conversation with history sent to backend
- REQ-CHAT-04: "New Chat" button to start fresh
- REQ-CHAT-05: Follow-up vs new question toggle (default: follow-up)
- REQ-CHAT-06: Clicking source references opens file in code viewer
- REQ-CHAT-07: Memory works silently (no visible memory UI)
- REQ-CHAT-08: Session-only (no persistence across reloads)

## Changes Required

### 1. Update API client (`frontend/src/lib/api.ts`)

- Update the `ask()` function to accept optional `conversation_history` parameter
- The `conversation_history` should be `Array<{ query: string; summary: string; files: string[] }>` matching the backend's expected format

### 2. New component: `ChatPanel.svelte` (`frontend/src/lib/ChatPanel.svelte`)

**Message Thread:**
- Scrollable message list, auto-scrolls to bottom on new messages
- User messages: right-aligned or left-aligned with "You" label, plain text
- Assistant messages: left-aligned with markdown rendering (using `marked`), source citations below
- Loading state: typing indicator or "Thinking..." while waiting for response
- Error messages displayed inline in red

**Source Citations in Responses:**
- Each source shows file path as a clickable link
- Clicking a source emits an event to open that file in the code viewer
- Show code snippet preview (collapsed by default, expandable)

**Input Area:**
- Fixed at bottom of the chat panel
- Textarea with Enter to submit, Shift+Enter for newline (same as current)
- "Ask" button, disabled while loading
- Follow-up mode toggle: small switch/button near the input, default ON
  - When ON: sends conversation_history with the request
  - When OFF: sends no history (fresh question)

**Chat Controls:**
- "New Chat" button in the header area, clears all messages and history

**State:**
- `messages: Array<{ role: 'user' | 'assistant'; content: string; sources?: Source[]; error?: boolean }>`
- `conversationHistory: Array<{ query: string; summary: string; files: string[] }>` — built from past Q&A pairs
- `followUpMode: boolean` — defaults to true
- `loading: boolean`

### 3. Layout restructure in `App.svelte`

**New Explorer Layout:**
- Left sidebar: FileTree (same as current, 240px)
- Center: ChatPanel (takes remaining space, flex-1)
- Right panel (conditional): CodeViewer, shown when a file is selected, closeable
  - Can be opened by clicking file in tree OR clicking source in chat
  - Close button to dismiss

**Header changes:**
- When in explorer, show project selector + "New Chat" button

### 4. Remove `QueryPanel.svelte`

- Delete the old QueryPanel component (replaced entirely by ChatPanel)

## Conversation History Format

The backend expects `conversation_history` as:
```json
[
  {"query": "What does main() do?", "summary": "Explains the main function...", "files": ["cmd/main.go"]},
  {"query": "How does the camera work?", "summary": "Camera uses ray tracing...", "files": ["tracer/camera.go"]}
]
```

After each successful response, append to history:
- `query`: the user's question
- `summary`: first 200 chars of the explanation (or the full thing if short)
- `files`: unique file_path values from the response sources

## Acceptance Criteria
- Chat conversation flows naturally with multiple Q&A exchanges
- Follow-up questions reference prior context by default
- Toggling off follow-up mode sends a standalone question
- "New Chat" clears the thread and history
- Clicking a source file_path in a response opens it in the code viewer
- Code viewer can be dismissed to return to full-width chat
- Auto-scrolls to latest message
- Markdown renders correctly in responses (code blocks, inline code, lists, etc.)
