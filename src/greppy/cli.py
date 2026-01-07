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
from .store import index_chunks, search, clear_index, get_stats, has_index

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """Greppy - Semantic code search powered by ChromaDB + Ollama."""
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Force reindex")
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

    # Check if already indexed
    if has_index(project_path) and not force:
        stats = get_stats(project_path)
        console.print(f"[yellow]Index already exists with {stats['chunks']} chunks.[/yellow]")
        console.print("Use [cyan]--force[/cyan] to reindex.")
        return

    console.print(f"[blue]Indexing {project_path}...[/blue]")

    # Collect chunks
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

    # Index chunks
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing...", total=None)

        total = index_chunks(project_path, chunks)
        progress.update(task, description=f"Indexed {total} chunks")

    console.print(f"[green]Done! Indexed {total} chunks.[/green]")


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
@click.option("--path", "-p", default=".", help="Path to search")
def exact(pattern: str, path: str):
    """Exact pattern search (uses ripgrep/grep)."""
    try:
        # Try ripgrep first
        result = subprocess.run(
            ["rg", "-n", "--color=never", pattern, path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(result.stdout)
        elif result.returncode == 1:
            print("No matches found.")
        else:
            raise FileNotFoundError()
    except FileNotFoundError:
        # Fallback to grep
        result = subprocess.run(
            ["grep", "-rn", pattern, path],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
        else:
            print("No matches found.")


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
