# Learnings

## Environment
- Python 3.14 is installed; `voyageai` package does not support Python >=3.13 in stable releases (only 0.2.x works, 0.3.x requires <3.14).
- A SOCKS/HTTP proxy is configured in the environment but is unreachable. pip installs require unsetting proxy env vars: `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org ...`
- `uv` (v0.9.16) is installed at `/opt/homebrew/bin/uv` but crashes in the Claude Code sandbox due to macOS `system-configuration` crate panicking (cannot read SCDynamicStore). Works fine outside sandbox. Prefer uv commands in AGENTS.md but fall back to pip in sandbox.
- When mocking LangChain classes like `ChatGoogleGenerativeAI`, mock at the import location (`codesherpa.llm.ChatGoogleGenerativeAI`) not the source module, since the constructor does network-dependent initialization.

## LLM
- Project uses Google Gemini (gemini-2.5-flash) via `langchain-google-genai`, not OpenAI.
