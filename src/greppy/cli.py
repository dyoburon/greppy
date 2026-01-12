"""Greppy CLI - Semantic code search."""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .embedder import check_ollama, check_model
from .chunker import chunk_codebase
from .store import (
    index_chunks,
    index_incremental,
    search,
    clear_index,
    get_stats,
    has_index,
    load_manifest,
    compute_changes,
)

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Greppy - Semantic code search powered by ChromaDB + Ollama."""
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Force full reindex")
def index(path: str, force: bool):
    """Index a codebase for semantic search."""
    project_path = Path(path).resolve()

    # Check prerequisites
    if not check_ollama():
        console.print("[red]Error: Ollama is not running.[/red]")
        console.print("Start it with: [cyan]ollama serve[/cyan]")
        sys.exit(1)

    if not check_model():
        console.print("[red]Error: Model 'nomic-embed-text' not found.[/red]")
        console.print("Pull it with: [cyan]ollama pull nomic-embed-text[/cyan]")
        sys.exit(1)

    # Check if we have an existing index with manifest
    has_existing = has_index(project_path)
    has_manifest = bool(load_manifest(project_path))

    # Decide: full index or incremental
    if force or not has_existing or not has_manifest:
        # Full reindex
        if force:
            console.print(f"[blue]Full reindex of {project_path}...[/blue]")
        else:
            console.print(f"[blue]Indexing {project_path}...[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning files...", total=None)
            chunks = list(chunk_codebase(project_path))
            progress.update(task, description=f"Found {len(chunks)} chunks")

        if not chunks:
            console.print("[yellow]No files found to index.[/yellow]")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Indexing...", total=None)
            total = index_chunks(project_path, chunks)
            progress.update(task, description=f"Indexed {total} chunks")

        console.print(f"[green]Done! Indexed {total} chunks.[/green]")

    else:
        # Incremental index
        added, modified, deleted = compute_changes(project_path)
        total_changes = len(added) + len(modified) + len(deleted)

        if total_changes == 0:
            stats = get_stats(project_path)
            console.print(f"[green]Index up to date ({stats['chunks']} chunks).[/green]")
            return

        console.print(f"[blue]Incremental update: {len(added)} new, {len(modified)} modified, {len(deleted)} deleted files[/blue]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Updating index...", total=None)
            added_chunks, deleted_chunks, files_updated = index_incremental(project_path)
            progress.update(task, description=f"Updated {files_updated} files")

        stats = get_stats(project_path)
        console.print(f"[green]Done! +{added_chunks} -{deleted_chunks} chunks (total: {stats['chunks']})[/green]")


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Number of results")
@click.option("--path", "-p", default=".", type=click.Path(exists=True), help="Project path")
def search_cmd(query: str, limit: int, path: str):
    """Semantic search across indexed codebase."""
    project_path = Path(path).resolve()

    # Check prerequisites
    if not check_ollama():
        console.print("[red]Error: Ollama is not running.[/red]")
        console.print("Start it with: [cyan]ollama serve[/cyan]")
        sys.exit(1)

    if not has_index(project_path):
        console.print("[yellow]Codebase not indexed.[/yellow]")
        console.print(f"Run: [cyan]greppy index {path}[/cyan]")
        sys.exit(1)

    results = search(project_path, query, limit)

    if not results:
        console.print("No results found.")
        return

    # Print results in grep-like format
    for r in results:
        score = f"[dim](score: {r['score']:.2f})[/dim]"
        location = f"[cyan]{r['file_path']}:{r['start_line']}[/cyan]"

        # Show first line of content
        first_line = r["content"].split("\n")[0][:100]
        console.print(f"{location}: {first_line} {score}")


# Alias 'search' command since Click doesn't allow 'search' as function name
main.add_command(search_cmd, name="search")


@main.command()
@click.argument("pattern")
@click.option("--limit", "-n", default=None, type=int, help="Max number of results")
@click.option("--ignore-case", "-i", is_flag=True, help="Case-insensitive search")
@click.option("--path", "-p", default=".", help="Path to search")
def exact(pattern: str, limit: int, ignore_case: bool, path: str):
    """Exact pattern search (uses ripgrep/grep)."""
    try:
        # Try ripgrep first
        cmd = ["rg", "-n", "--color=never", pattern, path]
        if ignore_case:
            cmd.insert(2, "-i")
        if limit:
            cmd.insert(2, f"--max-count={limit}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            output = result.stdout
            if limit:
                # Limit total lines of output
                lines = output.strip().split("\n")
                output = "\n".join(lines[:limit])
            print(output)
        elif result.returncode == 1:
            print("No matches found.")
        else:
            raise FileNotFoundError()
    except FileNotFoundError:
        # Fallback to grep
        cmd = ["grep", "-rn", pattern, path]
        if ignore_case:
            cmd.insert(2, "-i")
        if limit:
            cmd.insert(2, f"-m{limit}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            output = result.stdout
            if limit:
                lines = output.strip().split("\n")
                output = "\n".join(lines[:limit])
            print(output)
        else:
            print("No matches found.")


@main.command()
@click.argument("location")
@click.option("--context", "-c", default=50, help="Lines of context (default: 50)")
def read(location: str, context: int):
    """Read file contents with context around a line.

    Usage:
        greppy read src/auth.py              # Read first 50 lines
        greppy read src/auth.py:45           # Read ~50 lines centered on line 45
        greppy read src/auth.py:30-80        # Read lines 30-80
        greppy read src/auth.py -c 100       # More context
    """
    # Parse location: file.py, file.py:line, or file.py:start-end
    if ":" in location:
        file_part, line_part = location.rsplit(":", 1)
        if "-" in line_part:
            # Range: file.py:30-80
            start_str, end_str = line_part.split("-", 1)
            try:
                start_line = int(start_str)
                end_line = int(end_str)
            except ValueError:
                console.print(f"[red]Invalid line range: {line_part}[/red]")
                sys.exit(1)
        else:
            # Single line: file.py:45
            try:
                center_line = int(line_part)
                half = context // 2
                start_line = max(1, center_line - half)
                end_line = center_line + half
            except ValueError:
                # Maybe it's part of the path (e.g., C:\path on Windows)
                file_part = location
                start_line = 1
                end_line = context
    else:
        file_part = location
        start_line = 1
        end_line = context

    file_path = Path(file_part)
    if not file_path.exists():
        console.print(f"[red]File not found: {file_part}[/red]")
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        sys.exit(1)

    total_lines = len(lines)

    # Clamp to file bounds
    start_line = max(1, start_line)
    end_line = min(total_lines, end_line)

    # Print header
    console.print(f"[dim]# {file_path} (lines {start_line}-{end_line} of {total_lines})[/dim]")

    # Print lines with line numbers
    for i in range(start_line - 1, end_line):
        line_num = i + 1
        line_content = lines[i].rstrip("\n\r")
        print(f"{line_num:6}\t{line_content}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def status(path: str):
    """Check indexing status."""
    project_path = Path(path).resolve()
    stats = get_stats(project_path)

    if stats["exists"]:
        console.print(f"[green]Index exists[/green]")
        console.print(f"  Project: {stats['project']}")
        console.print(f"  Chunks: {stats['chunks']}")

        # Show pending changes
        added, modified, deleted = compute_changes(project_path)
        if added or modified or deleted:
            console.print(f"  [yellow]Pending: +{len(added)} ~{len(modified)} -{len(deleted)} files[/yellow]")
        else:
            console.print(f"  [dim]Up to date[/dim]")
    else:
        console.print(f"[yellow]No index found[/yellow]")
        console.print(f"  Project: {stats['project']}")
        console.print(f"Run: [cyan]greppy index {path}[/cyan]")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def clear(path: str):
    """Clear the search index."""
    project_path = Path(path).resolve()
    clear_index(project_path)
    console.print(f"[green]Index cleared for {project_path}[/green]")


if __name__ == "__main__":
    main()
