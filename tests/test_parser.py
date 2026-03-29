"""Tests for the code parsing pipeline."""

import os

import pytest

from codesherpa.parser import parse_codebase, parse_file, walk_directory


@pytest.fixture
def sample_tree(tmp_path):
    """Create a sample directory tree with source files."""
    # Python file with function and class
    py_file = tmp_path / "main.py"
    py_file.write_text(
        'def greet(name):\n    return f"Hello, {name}"\n\n\n'
        "class Greeter:\n    def __init__(self, name):\n        self.name = name\n\n"
        "    def say_hello(self):\n        return greet(self.name)\n"
    )

    # JavaScript file
    js_dir = tmp_path / "src"
    js_dir.mkdir()
    js_file = js_dir / "app.js"
    js_file.write_text(
        "function add(a, b) {\n    return a + b;\n}\n\n"
        "class Calculator {\n    multiply(a, b) {\n        return a * b;\n    }\n}\n"
    )

    # Hidden directory (should be skipped)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("gitconfig")

    # node_modules (should be skipped)
    nm_dir = tmp_path / "node_modules"
    nm_dir.mkdir()
    (nm_dir / "pkg.js").write_text("module.exports = {}")

    # __pycache__ (should be skipped)
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "main.cpython-311.pyc").write_bytes(b"\x00\x00")

    # Binary file (should be skipped)
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    # Documentation file (should be included)
    (tmp_path / "README.md").write_text("# My Project\n\nThis is a sample project.")

    return tmp_path


class TestWalkDirectory:
    """Tests for file tree walking."""

    def test_finds_source_files(self, sample_tree):
        files = walk_directory(str(sample_tree))
        basenames = {os.path.basename(f) for f in files}
        assert "main.py" in basenames
        assert "app.js" in basenames

    def test_skips_hidden_directories(self, sample_tree):
        files = walk_directory(str(sample_tree))
        for f in files:
            assert ".git" not in f.split(os.sep)

    def test_skips_node_modules(self, sample_tree):
        files = walk_directory(str(sample_tree))
        for f in files:
            assert "node_modules" not in f.split(os.sep)

    def test_skips_pycache(self, sample_tree):
        files = walk_directory(str(sample_tree))
        for f in files:
            assert "__pycache__" not in f.split(os.sep)

    def test_skips_binary_files(self, sample_tree):
        files = walk_directory(str(sample_tree))
        extensions = {os.path.splitext(f)[1] for f in files}
        assert ".png" not in extensions

    def test_includes_documentation_files(self, sample_tree):
        files = walk_directory(str(sample_tree))
        basenames = {os.path.basename(f) for f in files}
        assert "README.md" in basenames

    def test_supports_multiple_languages(self, tmp_path):
        extensions = [
            ".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".rb",
            ".zig", ".cs", ".kt", ".swift", ".scala", ".php", ".lua",
            ".md", ".rst",
        ]
        for ext in extensions:
            (tmp_path / f"file{ext}").write_text("// code")
        files = walk_directory(str(tmp_path))
        found_ext = {os.path.splitext(f)[1] for f in files}
        assert found_ext == set(extensions)


class TestParseFile:
    """Tests for parsing individual source files."""

    def test_python_function_chunks(self, tmp_path):
        py_file = tmp_path / "funcs.py"
        py_file.write_text("def foo():\n    pass\n\n\ndef bar():\n    pass\n")
        chunks = parse_file(str(py_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(func_chunks) == 2
        assert any("foo" in c.content for c in func_chunks)
        assert any("bar" in c.content for c in func_chunks)

    def test_python_class_chunks(self, tmp_path):
        py_file = tmp_path / "classes.py"
        py_file.write_text(
            "class MyClass:\n    def method(self):\n        pass\n"
        )
        chunks = parse_file(str(py_file), str(tmp_path))
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(class_chunks) == 1
        assert "MyClass" in class_chunks[0].content

    def test_python_module_chunk_for_top_level_code(self, tmp_path):
        py_file = tmp_path / "module.py"
        py_file.write_text("import os\nimport sys\n\nX = 42\n\ndef func():\n    pass\n")
        chunks = parse_file(str(py_file), str(tmp_path))
        module_chunks = [c for c in chunks if c.chunk_type == "module"]
        assert len(module_chunks) == 1
        assert "X = 42" in module_chunks[0].content

    def test_chunk_metadata_correct(self, tmp_path):
        py_file = tmp_path / "meta.py"
        source = "def hello():\n    print('hi')\n"
        py_file.write_text(source)
        chunks = parse_file(str(py_file), str(tmp_path))
        func_chunk = [c for c in chunks if c.chunk_type == "function"][0]
        assert func_chunk.file_path == "meta.py"
        assert func_chunk.language == "python"
        assert func_chunk.start_char >= 0
        assert func_chunk.end_char <= len(source)
        assert source[func_chunk.start_char : func_chunk.end_char] == func_chunk.content

    def test_js_function_and_class_chunks(self, tmp_path):
        js_file = tmp_path / "app.js"
        js_file.write_text(
            "function add(a, b) {\n    return a + b;\n}\n\n"
            "class Calc {\n    sub(a, b) {\n        return a - b;\n    }\n}\n"
        )
        chunks = parse_file(str(js_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "javascript"

    def test_zig_function_and_struct_chunks(self, tmp_path):
        zig_file = tmp_path / "main.zig"
        zig_file.write_text(
            "const std = @import(\"std\");\n\n"
            "pub const Point = struct {\n    x: f32,\n    y: f32,\n};\n\n"
            "pub fn add(a: i32, b: i32) i32 {\n    return a + b;\n}\n"
        )
        chunks = parse_file(str(zig_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "zig"

    def test_csharp_function_and_class_chunks(self, tmp_path):
        cs_file = tmp_path / "Program.cs"
        cs_file.write_text(
            "using System;\n\n"
            "public class Calculator {\n"
            "    public int Add(int a, int b) {\n        return a + b;\n    }\n"
            "}\n"
        )
        chunks = parse_file(str(cs_file), str(tmp_path))
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(class_chunks) >= 1
        assert "Calculator" in class_chunks[0].content
        assert chunks[0].language == "csharp"

    def test_kotlin_function_and_class_chunks(self, tmp_path):
        kt_file = tmp_path / "Main.kt"
        kt_file.write_text(
            "fun greet(name: String): String {\n    return \"Hello, $name\"\n}\n\n"
            "data class User(val name: String, val age: Int)\n"
        )
        chunks = parse_file(str(kt_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "kotlin"

    def test_swift_function_and_class_chunks(self, tmp_path):
        swift_file = tmp_path / "main.swift"
        swift_file.write_text(
            "func add(_ a: Int, _ b: Int) -> Int {\n    return a + b\n}\n\n"
            "struct Point {\n    var x: Double\n    var y: Double\n}\n"
        )
        chunks = parse_file(str(swift_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "swift"

    def test_scala_function_and_class_chunks(self, tmp_path):
        scala_file = tmp_path / "Main.scala"
        scala_file.write_text(
            "def add(a: Int, b: Int): Int = {\n  a + b\n}\n\n"
            "case class Point(x: Double, y: Double)\n"
        )
        chunks = parse_file(str(scala_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "scala"

    def test_php_function_and_class_chunks(self, tmp_path):
        php_file = tmp_path / "app.php"
        php_file.write_text(
            "<?php\n\n"
            "function greet($name) {\n    return \"Hello, $name\";\n}\n\n"
            "class Greeter {\n"
            "    public function sayHello() {\n        return 'hi';\n    }\n"
            "}\n"
        )
        chunks = parse_file(str(php_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        class_chunks = [c for c in chunks if c.chunk_type == "class"]
        assert len(func_chunks) >= 1
        assert len(class_chunks) >= 1
        assert chunks[0].language == "php"

    def test_lua_function_chunks(self, tmp_path):
        lua_file = tmp_path / "main.lua"
        lua_file.write_text(
            "function add(a, b)\n    return a + b\nend\n\n"
            "local function multiply(a, b)\n    return a * b\nend\n"
        )
        chunks = parse_file(str(lua_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        assert len(func_chunks) >= 2
        assert any("add" in c.content for c in func_chunks)
        assert any("multiply" in c.content for c in func_chunks)
        assert chunks[0].language == "lua"

    def test_markdown_file_parsed_as_document(self, tmp_path):
        """Markdown files are parsed as a single document chunk."""
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# My Project\n\nThis project does XYZ.\n\n"
            "## Setup\n\nRun `npm install`.\n"
        )
        chunks = parse_file(str(md_file), str(tmp_path))
        assert len(chunks) >= 1
        assert chunks[0].language == "markdown"
        assert chunks[0].chunk_type == "document"
        assert "My Project" in chunks[0].content

    def test_go_top_level_code_captured(self, tmp_path):
        """Go files should capture package, imports, and type definitions as module chunk."""
        go_file = tmp_path / "main.go"
        go_file.write_text(
            'package main\n\n'
            'import "fmt"\n\n'
            'type Point struct {\n'
            '    X, Y float64\n'
            '}\n\n'
            'func main() {\n'
            '    fmt.Println("hello")\n'
            '}\n'
        )
        chunks = parse_file(str(go_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        module_chunks = [c for c in chunks if c.chunk_type == "module"]
        assert len(func_chunks) == 1
        assert "main" in func_chunks[0].content
        assert len(module_chunks) == 1
        assert "package main" in module_chunks[0].content
        assert 'import "fmt"' in module_chunks[0].content

    def test_chunk_contains_complete_code(self, tmp_path):
        """Each chunk should contain a complete, coherent unit of code."""
        py_file = tmp_path / "complete.py"
        py_file.write_text(
            "def outer():\n"
            "    def inner():\n"
            "        return 1\n"
            "    return inner()\n"
        )
        chunks = parse_file(str(py_file), str(tmp_path))
        func_chunks = [c for c in chunks if c.chunk_type == "function"]
        # outer function should contain inner function
        assert len(func_chunks) == 1
        assert "inner" in func_chunks[0].content
        assert "outer" in func_chunks[0].content


class TestErrorHandling:
    """Tests for error handling during parsing."""

    def test_syntax_error_logged_and_skipped(self, tmp_path):
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n    # missing closing paren")

        good_file = tmp_path / "good.py"
        good_file.write_text("def working():\n    pass\n")

        chunks, errors = parse_codebase(str(tmp_path))
        # Good file should still produce chunks
        assert any("working" in c.content for c in chunks)
        # Bad file should be in errors
        assert len(errors) >= 1
        assert any("bad.py" in e for e in errors)

    def test_pipeline_continues_after_error(self, tmp_path):
        """A single file failure should not abort the pipeline."""
        # Create multiple files, one broken
        for i in range(5):
            (tmp_path / f"good_{i}.py").write_text(f"def func_{i}():\n    pass\n")
        (tmp_path / "broken.py").write_text("class Incomplete(:\n    pass")

        chunks, errors = parse_codebase(str(tmp_path))
        assert len(chunks) >= 5  # All good files parsed
        assert len(errors) == 1


class TestProgressDisplay:
    """Tests for progress reporting."""

    def test_progress_callback_called(self, tmp_path):
        (tmp_path / "a.py").write_text("def a():\n    pass\n")
        (tmp_path / "b.py").write_text("def b():\n    pass\n")

        progress_updates = []

        def on_progress(files_processed, chunks_created, errors_count):
            progress_updates.append((files_processed, chunks_created, errors_count))

        parse_codebase(str(tmp_path), progress_callback=on_progress)
        # Should have been called at least once per file
        assert len(progress_updates) >= 2
        # Last update should reflect final state
        last = progress_updates[-1]
        assert last[0] == 2  # 2 files processed
        assert last[1] >= 2  # at least 2 chunks
        assert last[2] == 0  # no errors
