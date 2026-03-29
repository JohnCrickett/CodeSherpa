import { createHighlighter, type Highlighter } from "shiki";

let highlighter: Highlighter | null = null;
let loading: Promise<Highlighter> | null = null;

const LANGS = [
  "python", "javascript", "typescript", "go", "rust", "java",
  "c", "cpp", "csharp", "kotlin", "swift", "scala", "php",
  "lua", "zig", "ruby", "html", "css", "json", "yaml", "toml",
  "markdown", "sql", "bash", "dockerfile",
];

async function getHighlighter(): Promise<Highlighter> {
  if (highlighter) return highlighter;
  if (!loading) {
    loading = createHighlighter({
      themes: ["github-dark", "github-light"],
      langs: LANGS,
    });
    highlighter = await loading;
  }
  return loading;
}

const EXT_TO_LANG: Record<string, string> = {
  py: "python", js: "javascript", ts: "typescript", jsx: "javascript",
  tsx: "typescript", go: "go", rs: "rust", java: "java", c: "c",
  cpp: "cpp", cc: "cpp", h: "c", hpp: "cpp", cs: "csharp",
  kt: "kotlin", swift: "swift", scala: "scala", php: "php",
  lua: "lua", zig: "zig", rb: "ruby", html: "html", css: "css",
  json: "json", yaml: "yaml", yml: "yaml", toml: "toml",
  md: "markdown", sql: "sql", sh: "bash", bash: "bash",
  dockerfile: "dockerfile",
};

export function langFromPath(filePath: string): string {
  const name = filePath.split("/").pop() ?? "";
  if (name.toLowerCase() === "dockerfile") return "dockerfile";
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TO_LANG[ext] ?? "text";
}

export async function highlight(
  code: string,
  lang: string,
  dark: boolean,
): Promise<string> {
  const hl = await getHighlighter();
  const theme = dark ? "github-dark" : "github-light";
  const resolvedLang = hl.getLoadedLanguages().includes(lang) ? lang : "text";
  return hl.codeToHtml(code, {
    lang: resolvedLang,
    theme,
  });
}
