# Coding Challenge - Code Sherpa

This challenge is to build your own semantic code exploration tool - a system that helps developers make sense of large, unfamiliar codebases using natural language questions instead of reading files top to bottom.

We've all been there. You join a new team, or pick up a legacy project, and you're staring at thousands of files with no idea where the interesting bits live. You grep for keywords, follow import chains, open file after file, and slowly piece together how things fit. It works, but it's slow and frustrating.

Code Sherpa takes a different approach. You point it at a codebase and ask questions in plain English: "where do we handle payment failures?" or "how does the authentication flow work?" The system finds the relevant code by meaning, not by keyword matching, explains what it does, and remembers what you've already explored so each session builds on the last.

Under the hood, the system parses code into semantic chunks, embeds them into vectors, and stores them in a vector database. When you ask a question, it retrieves the most relevant code using both vector similarity and full-text search, and uses an LLM to explain it in context. The agentic behaviour - memory, follow-up questions, multi-step exploration - is orchestrated using LangGraph's state machine model, while LangChain handles the retrieval chains and LLM integration. It's a practical introduction to vector search, full-text search, embeddings, code parsing, agent orchestration, and building a web interface to tie it all together.

## The Challenge - Building Code Sherpa

You're going to build a semantic code exploration tool. It starts by ingesting a codebase into a vector database, then lets you query it through a web interface using natural language. Step by step you'll add code parsing, vector storage, semantic retrieval, LLM-powered explanations, project management, a web interface, agent memory, and intelligent navigation. By the end, you'll have a tool that genuinely helps you understand unfamiliar code.

### Step Zero

In this introductory step you're going to set your environment up ready to begin developing and testing your solution.

You'll need to make a few decisions and get some infrastructure running:

1. **Set up your vector database.** You'll need Oracle Database 26ai running in a local Docker container. Pull the `container-registry.oracle.com/database/free:latest` image, start the container, and set a password for the admin account. You can find full setup instructions in the [Oracle Database Free Get Started guide](https://www.oracle.com/uk/database/free/get-started/). Once the container is running, connect using a SQL client and verify you can create a table. Store all credentials in an environment file, not hardcoded anywhere.

   ```bash
   docker pull container-registry.oracle.com/database/free:latest
   docker run -d -p 1521:1521 -e ORACLE_PASSWORD=<your-password> container-registry.oracle.com/database/free:latest
   ```

2. **Choose your embedding model.** You need a code-aware embedding model - one that understands programming constructs, not just prose. Voyage AI's `voyage-code-3` is purpose-built for code and understands syntax, control flow, and naming conventions across many languages. It produces 1024-dimensional vectors. You'll need an API key from Voyage AI.

3. **Set up your LLM provider.** You'll need a language model for generating explanations later. Any provider with a chat API will work - Anthropic, OpenAI, Google, Mistral, or a local model.

4. **Set up LangChain and LangGraph.** You'll be using LangChain for retrieval chains and LLM integration, and LangGraph for orchestrating the agent's behaviour as a state machine. Install both: `pip install langchain langgraph`. LangChain handles the plumbing of embedding, retrieval, and prompting. LangGraph handles the agentic flow - deciding when to search memory, when to retrieve code, when to ask follow-up questions, and how to route between these steps.

Prepare a test codebase to work with throughout the challenge. Pick an open source project you're curious about but haven't explored in depth - something with a few thousand lines across multiple files and directories. A project with clear structure (like a web framework, CLI tool, or library) works well.

**Testing:** Verify your Oracle Database container is running and you can connect to it. Make a test call to the Voyage AI embedding API and your LLM API to confirm both return valid responses. Verify your environment file is being read correctly and no credentials are in your source code.

### Step 1

In this step your goal is to build a code parsing pipeline that breaks a codebase into meaningful chunks.

The foundation of semantic code search is good chunking. Rather than splitting files at arbitrary character boundaries, you want to split at logical boundaries: functions, classes, and modules. A chunk should represent one coherent unit of code that makes sense on its own.

Point your parser at a local directory and have it walk the file tree, identify source files, and split each one into chunks. Each chunk should carry metadata: the file path it came from, what type of chunk it is (function, class, module), the programming language, and the character range within the original file.

Not every file will parse cleanly. Some might have syntax errors, use unusual language features, or be in a format your parser doesn't support. When that happens, log the failure and keep going. A partial index is far more useful than no index at all.

Display progress in the terminal as ingestion runs: how many files have been processed, how many chunks have been created, and any failures encountered.

**Testing:**
- Run your parser against your test codebase and verify it produces chunks at function and class boundaries, not arbitrary splits.
- Inspect several chunks and confirm each one contains a complete, coherent unit of code.
- Check that the metadata on each chunk is correct - file path, chunk type, language, and character range should all match the source.
- Introduce a file with a deliberate syntax error and verify the parser logs the failure and continues processing the rest.
- Verify the terminal output shows meaningful progress: files processed, chunks created, and any errors.

### Step 2

In this step your goal is to embed the code chunks and store them in your vector database.

Take each chunk from your parser, generate a vector embedding for it using `voyage-code-3`, and store the embedding alongside the chunk's text and metadata in Oracle Database. The metadata fields - file path, chunk type, language, and character range - should all be stored and indexed so you can filter on them later.

Think about how you structure your storage. You'll want to be able to search by vector similarity, but also filter by metadata (e.g. "only show me Python files" or "only functions, not classes"). Set up your vector indexes accordingly. Also create an Oracle Text full-text index on the code text column - this will let you fall back to keyword search when vector similarity alone doesn't find good matches, and is particularly useful when developers search for exact identifier names, error messages, or string literals.

**Testing:**
- Run the full pipeline - parse then embed and store - against your test codebase.
- Query Oracle Database directly to verify the data is there: check the total number of stored chunks matches what your parser reported.
- Inspect a few stored entries and confirm they contain the embedding vector, the original code text, and all metadata fields.
- Verify that both the vector index and the full-text index have been created on the appropriate columns.
- Run the pipeline again against the same codebase and verify it handles the re-run sensibly (either updating existing entries or skipping duplicates).

### Step 3

In this step your goal is to implement semantic retrieval so you can ask natural language questions and get back the most relevant code.

This is where the tool starts to feel useful. Take a natural language question from the user, embed it using `voyage-code-3`, and search your vector database for the closest matches using cosine similarity. Also run the query through Oracle Text full-text search on the same table. Combine the results - vector search finds semantically related code even when the words don't match, while full-text search catches exact identifier names and string literals that vector search might rank lower. Return the top results along with their file paths and line references.

Not every query will have good matches. Set a minimum cosine similarity threshold of around 0.3 for `voyage-code-3` embeddings - results below this score are unlikely to be meaningfully related to the query. You may need to adjust this based on your codebase: if you're getting too many irrelevant results, raise it; if you're missing relevant code, lower it. When nothing exceeds the threshold and full-text search also returns no matches, the system should tell the user honestly rather than returning low-confidence results that waste their time.

Build this as a simple CLI interface for now - you'll add the web interface later. The user types a question, and the system returns the matching code chunks with their locations.

**Testing:**
- Ask a question about something you know exists in your test codebase (e.g. "where is the main entry point?" or "how are errors handled?"). Verify the returned chunks are genuinely relevant.
- Ask the same question using different phrasing and verify you get similar results. This is the whole point of semantic search - it matches by meaning, not keywords.
- Search for an exact function or variable name. Verify the full-text search catches it even if the vector similarity score would be low.
- Ask a question about something that definitely isn't in the codebase. Verify the system tells you no relevant code was found rather than returning irrelevant results.
- Check that every returned chunk includes its file path and line reference.

### Step 4

In this step your goal is to add LLM-powered explanations so the system doesn't just find code - it explains what the code does.

Raw code chunks are useful, but an explanation in plain language is far more helpful when you're trying to understand an unfamiliar codebase. Wire up your LLM through LangChain to take the retrieved chunks and generate a clear explanation. Use LangChain's retrieval chain to handle the prompt construction - passing the retrieved code as context alongside the user's question.

The explanation should cite the specific functions and files involved. When the user asks how two parts of the codebase relate to each other, the system should retrieve both and explain the connection. Where multiple implementations of the same concept exist, it should surface all of them and explain the differences.

Crucially, the system should not speculate beyond what the retrieved code supports. If a question can't be fully answered from what's been ingested, it should say so explicitly rather than making things up.

**Testing:**
- Ask what a specific function does. The explanation should be accurate, in plain language, and cite the file and function name.
- Ask how two parts of the codebase relate (e.g. "how does the router connect to the request handlers?"). The system should retrieve relevant code from both areas and explain the relationship.
- Ask a question that the codebase only partially answers. Verify the system explains what it can and explicitly flags what it can't determine from the code.
- Ask about a concept that has multiple implementations in the codebase. Verify the system surfaces all of them and explains how they differ.

### Step 5

In this step your goal is to add project management so a developer can maintain separate knowledge bases for different codebases.

A developer working across multiple projects needs each one indexed and searchable independently. Add support for named projects. Store project metadata - name, source path, creation date, last ingestion timestamp, file count, and chunk count - in Oracle Database alongside your embeddings. Each project should store its embeddings, metadata, and any agent memory in isolation, so queries against one project never return results from another.

The user should be able to create a new project, list existing projects, and select which project to query. When a codebase is re-ingested into an existing project, only the changed files should be re-embedded - unchanged files should keep their existing embeddings. This makes re-ingestion fast even for large projects.

All project data should persist between runs in Oracle Database. When the user comes back tomorrow and selects a project, everything should be exactly as they left it.

**Testing:**
- Create two projects from two different codebases. Query each one and verify the results come only from the correct project.
- List your projects and verify both appear with the correct names and metadata (source path, file count, last ingestion time).
- Query the project metadata directly in Oracle Database and verify it matches what the system reports.
- Modify a single file in one of your test codebases, re-ingest, and verify that only the changed file's chunks are re-embedded. Unchanged files should not be re-processed.
- Stop and restart your system. Verify all project data is still intact and queryable.

### Step 6

In this step your goal is to build a web interface for browsing and querying your indexed codebases.

The web interface should launch automatically when the system starts, opening in the default browser or displaying the local URL clearly in the terminal. It needs a few key pieces: a way to select and switch between projects, a conversational query panel for asking questions, and a display that shows retrieved code chunks alongside the agent's explanation with file paths and line references.

Add a browsable file tree of the ingested codebase structure, built from the stored metadata. This gives the user a visual overview of the project layout without needing to look at the actual file system.

While the agent is processing a query, show a loading state so the user knows something is happening.

**Testing:**
- Start the system and verify the web interface launches and is accessible in your browser.
- Select a project and ask a question through the query panel. Verify the response shows code chunks with file paths and line references alongside the explanation.
- Switch between projects and verify the results update to reflect the selected project.
- Browse the file tree and verify it accurately reflects the structure of the ingested codebase.
- Submit a query and verify a loading indicator appears while the response is being generated.

### Step 7

In this step your goal is to add agent memory so the system remembers what's been explored and what the developer has told it about the project.

Without memory, every session starts from scratch. The developer re-explains the same context, re-asks the same orientation questions, and the system re-explains things it's already covered. Memory changes that.

Implement two types of memory, stored in Oracle Database alongside your code embeddings. Episodic memory tracks which areas of the codebase the developer has already explored, so the system can avoid re-explaining concepts that have already been covered. Semantic memory stores project-level context that the developer provides - things like "this service owns all payment logic" or "the legacy auth module is being deprecated" - and applies it to future responses within that project.

Use LangGraph to build a memory-aware query graph. When a question arrives, the graph should first check memory for relevant prior context, then decide how to handle the query: if the user has already explored this area, route to a node that builds on prior understanding rather than explaining from scratch; if it's new territory, route to a full retrieval and explanation. This routing logic is where LangGraph's state machine model pays off - each node in the graph handles one concern (check memory, retrieve code, generate explanation, update memory) and the edges encode the decision logic.

Since you already have Oracle Database storing your code embeddings, it's a natural home for memory too. Store memory entries as vectors so they can be retrieved by semantic similarity - when a developer asks a question, the system can search its memory for relevant prior context the same way it searches the codebase for relevant code. Keep memory isolated per project, just like your code embeddings.

Both types of memory should persist across sessions in Oracle Database. When the user returns to a project, the system should pick up where it left off. When asked, the system should be able to provide a summary of what's been explored so far and what remains unvisited.

**Testing:**
- Explore several areas of a codebase across a session. End the session, start a new one, and ask the system what you've explored so far. It should accurately summarise the areas you've already covered.
- Tell the system something about the project (e.g. "the payments module is the most critical part of this service"). In subsequent queries, verify the system uses this context to inform its responses.
- Ask about something you've already explored. The system should recognise this and build on prior understanding rather than explaining from scratch.
- Ask for a summary of what's been explored versus what remains unvisited. Verify it gives a reasonable breakdown.

### Step 8

In this step your goal is to add intelligent navigation so developers can drill deeper into code and follow connections naturally.

A good exploration tool doesn't just answer isolated questions - it helps you follow threads. Use LangGraph to model multi-step retrieval as a state graph. When a user asks "what calls this?", the graph should: retrieve the current function's code, identify references to it across the codebase, retrieve those callers, and generate an explanation that ties them together. Each step is a node in the graph, with state passed between them.

Add support for follow-up questions that drill deeper into a previous result without the user needing to re-state context. If the system just explained a function, the user should be able to ask "what calls this?" or "where is the return value used?" and get a meaningful answer. LangGraph's state carries the conversation context forward, so the agent knows which function is being discussed.

When the system identifies a dependency or reference in retrieved code - an import, a function call, an inherited class - it should offer to retrieve and explain the linked code. In the web interface, render these as clickable elements that trigger a follow-up retrieval.

Add an exploration planning capability using LangGraph. When a user asks a broad question like "how does the authentication system work?", the agent should plan a multi-step exploration: find entry points, trace the authentication flow through the codebase, retrieve each step, and produce a coherent walkthrough. Model this as a graph where each retrieval step feeds into the next, building up a complete picture rather than returning a single set of search results.

Finally, add a "map" query that returns a high-level summary of the codebase structure: a breakdown of languages used, top-level modules, and entry points where identifiable. This gives the developer a bird's-eye view before diving into specifics.

**Testing:**
- Ask about a function, then ask a follow-up like "what calls this?" without re-stating which function you mean. The system should understand from context and return relevant results.
- Look for linked dependencies in a response. If the system identifies an import or function call, verify it offers to explain the linked code.
- In the web interface, click a dependency link and verify it triggers a follow-up retrieval and explanation.
- Run the "map" query and verify you get a useful high-level summary: languages, modules, and entry points should all be represented.
