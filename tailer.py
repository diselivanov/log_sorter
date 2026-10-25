import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class LogTailer:
    def __init__(self, paths, on_line):
        self.paths = [os.path.abspath(p) for p in paths]
        self.on_line = on_line
        self.handles = {}
        self.dirs = set(os.path.dirname(p) for p in self.paths)
        self.observer = None
        self._first_start = True
        self._open_all()

    def _open_all(self):
        for p in self.paths:
            self._open(p, at_end=self._first_start)
        self._first_start = False

    def _open(self, path, at_end=True):
        try:
            f = open(path, "r", encoding="utf-8", errors="replace")
            if at_end:
                f.seek(0, os.SEEK_END)
            self.handles[path] = (f, f.tell())
        except FileNotFoundError:
            self.handles[path] = (None, 0)

    def read_new(self):
        for path in self.paths:
            f, offset = self.handles.get(path, (None, 0))

            if not os.path.exists(path):
                if f:
                    f.close()
                self.handles[path] = (None, 0)
                continue

            if f is None:
                self._open(path, at_end=False)
                f, offset = self.handles[path]
                if f is None:
                    continue

            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue

            # ротация: сменился inode
            if st.st_ino != os.fstat(f.fileno()).st_ino:
                f.close()
                self._open(path, at_end=False)
                f, offset = self.handles[path]
                if f is None:
                    continue

            # усечение
            if st.st_size < offset:
                f.seek(0)
                offset = 0

            f.seek(offset)
            for line in f:
                self.on_line(line)
            self.handles[path] = (f, f.tell())

    def start(self):
        class Handler(FileSystemEventHandler):
            def __init__(self, tailer):
                self.tailer = tailer

            def on_any_event(self, event):
                self.tailer.read_new()

        self.observer = Observer()
        handler = Handler(self)
        for d in self.dirs:
            if os.path.isdir(d):
                self.observer.schedule(handler, d, recursive=False)
        self.observer.start()

        try:
            while True:
                self.read_new()
                time.sleep(2)
        except KeyboardInterrupt:
            pass
        finally:
            self.observer.stop()
            self.observer.join()
            for f, _ in self.handles.values():
                if f:
                    f.close()
