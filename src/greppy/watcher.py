"""File system watcher for automatic indexing."""

import time
import threading
from pathlib import Path
from typing import Set, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .chunker import CODE_EXTENSIONS, SKIP_DIRS


class CodeChangeHandler(FileSystemEventHandler):
    """Handler for code file changes with debouncing."""

    def __init__(
        self,
        project_path: Path,
        on_change: Callable[[Path], None],
        debounce_seconds: float = 5.0,
    ):
        self.project_path = project_path
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored."""
        path_parts = Path(path).parts
        for part in path_parts:
            if part in SKIP_DIRS or part.startswith("."):
                return True
        return False

    def _is_code_file(self, path: str) -> bool:
        """Check if file is a code file we should track."""
        if self._should_ignore(path):
            return False
        ext = Path(path).suffix.lower()
        return ext in CODE_EXTENSIONS

    def _schedule_index(self):
        """Schedule an index run after debounce period."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(
                self.debounce_seconds,
                self._run_index,
            )
            self._timer.start()

    def _run_index(self):
        """Run the index callback."""
        with self._lock:
            self._timer = None
        self.on_change(self.project_path)

    def on_modified(self, event: FileSystemEvent):
        if not event.is_directory and self._is_code_file(event.src_path):
            self._schedule_index()

    def on_created(self, event: FileSystemEvent):
        if not event.is_directory and self._is_code_file(event.src_path):
            self._schedule_index()

    def on_deleted(self, event: FileSystemEvent):
        if not event.is_directory and self._is_code_file(event.src_path):
            self._schedule_index()

    def on_moved(self, event: FileSystemEvent):
        if not event.is_directory:
            if self._is_code_file(event.src_path) or self._is_code_file(event.dest_path):
                self._schedule_index()

    def stop(self):
        """Cancel any pending timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None


class Watcher:
    """Watches a directory for code changes and triggers indexing."""

    def __init__(
        self,
        project_path: Path,
        on_change: Callable[[Path], None],
        debounce_seconds: float = 5.0,
    ):
        self.project_path = project_path.resolve()
        self.debounce_seconds = debounce_seconds
        self.on_change = on_change
        self._observer: Observer | None = None
        self._handler: CodeChangeHandler | None = None

    def start(self):
        """Start watching for changes."""
        self._handler = CodeChangeHandler(
            self.project_path,
            self.on_change,
            self.debounce_seconds,
        )
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self.project_path),
            recursive=True,
        )
        self._observer.start()

    def stop(self):
        """Stop watching."""
        if self._handler:
            self._handler.stop()
        if self._observer:
            self._observer.stop()
            self._observer.join()

    def wait(self):
        """Wait for the observer to finish."""
        if self._observer:
            try:
                while self._observer.is_alive():
                    self._observer.join(1)
            except KeyboardInterrupt:
                self.stop()
