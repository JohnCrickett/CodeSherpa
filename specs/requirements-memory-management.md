# Requirements Specification: Memory Management Page

## Context

CodeSherpa stores two types of agent memory per project: **episodic memory** (auto-tracked exploration history: queries asked, files explored, summaries) and **semantic memory** (developer-provided project context like "this service owns all payment logic"). The existing backend supports storing, searching, listing, and deleting these memories, but the web UI has no dedicated interface for browsing or managing them.

This feature adds a new top-level **Memory** page (alongside the existing Explorer and Projects pages) where the user can select a project, then search, view, add to, edit, and delete memory entries for that project.

References: Task 08 (Agent Memory), existing `memory.py` backend, existing memory API endpoints in `web.py`.

---

## Requirements

### Navigation

**REQ-MEM-01:** The web interface shall provide a top-level "Memory" navigation button in the header, alongside the existing "Explorer" and "Projects" buttons.

**REQ-MEM-02:** When the user navigates to the Memory page, it shall display a project selector allowing the user to pick which project's memory to manage.

**REQ-MEM-03:** If the user has a project selected in the Explorer, navigating to the Memory page shall pre-select that project.

### Memory Display

**REQ-MEM-04:** When a project is selected, the Memory page shall display two sections: "Episodic Memory" (exploration history) and "Semantic Memory" (project context).

**REQ-MEM-05:** The Episodic Memory section shall list all episodic memory entries for the selected project, showing for each entry: the query that was asked, the files that were explored, the summary, and the timestamp.

**REQ-MEM-06:** The Semantic Memory section shall list all semantic memory entries for the selected project, showing for each entry: the content and the timestamp.

**REQ-MEM-07:** Both sections shall display a count of total entries.

### Search

**REQ-MEM-08:** The Memory page shall provide a single search input that searches across both episodic and semantic memory simultaneously.

**REQ-MEM-09:** Search shall perform both text-based filtering (substring match on memory content/queries) and semantic search (vector similarity using the existing embedding infrastructure) and return a consolidated, deduplicated set of results.

**REQ-MEM-10:** Search results shall be displayed in a unified list, with each result clearly labeled as either "episodic" or "semantic" and showing the relevant fields for its type.

**REQ-MEM-11:** When search is cleared, the page shall return to showing the full list view with both sections.

### Add Semantic Memory

**REQ-MEM-12:** The Memory page shall provide a form to add new semantic memory entries for the selected project.

**REQ-MEM-13:** When the user submits the form with non-empty content, the system shall store the semantic memory entry (embedding it for future retrieval) and display it in the semantic memory list.

**REQ-MEM-14:** When the user submits empty content, the system shall display a validation error without creating an entry.

### Edit Semantic Memory

**REQ-MEM-15:** Each semantic memory entry shall have an "Edit" action that allows the user to modify its content.

**REQ-MEM-16:** When the user saves an edited semantic memory entry, the system shall delete the old entry and create a new one with the updated content (re-embedding it for future retrieval). The entry shall appear updated in the list.

**REQ-MEM-17:** The edit form shall allow cancellation, returning to the display state without changes.

### Delete Individual Entries

**REQ-MEM-18:** Each semantic memory entry shall have a "Delete" action.

**REQ-MEM-19:** Each episodic memory entry shall have a "Delete" action.

**REQ-MEM-20:** When the user clicks delete on an individual entry, the system shall remove it from the database and update the displayed list.

### Bulk Delete

**REQ-MEM-21:** The Memory page shall provide a "Clear All Episodic Memory" action for the selected project.

**REQ-MEM-22:** The Memory page shall provide a "Clear All Semantic Memory" action for the selected project.

**REQ-MEM-23:** The Memory page shall provide a "Clear All Memory" action that deletes both episodic and semantic memory for the selected project.

**REQ-MEM-24:** All bulk delete actions shall require explicit confirmation before executing. The confirmation shall clearly state what will be deleted and that the action is irreversible.

### Error Handling

**REQ-MEM-25:** When any memory operation fails (search, add, edit, delete, bulk delete), the system shall display a descriptive error message to the user.

**REQ-MEM-26:** Failed operations shall not leave the UI in an inconsistent state — the displayed data shall remain accurate.

---

## Acceptance Criteria

1. A user can navigate to the Memory page from the header and see a project selector.
2. After selecting a project, the user sees both episodic and semantic memory entries listed with all relevant fields.
3. A user can search memory using a text query and get consolidated results from both memory types, using both substring and semantic matching.
4. A user can add a new semantic memory entry and see it appear in the list.
5. A user can edit an existing semantic memory entry (delete + re-create with new content).
6. A user can delete individual episodic or semantic memory entries.
7. A user can bulk-clear all episodic memory, all semantic memory, or all memory for a project, with confirmation required.
8. Error cases display clear messages without corrupting the displayed state.
9. The Memory page pre-selects the project if one was already selected in the Explorer.
