import os
import re
import yaml


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_paths(path: str) -> tuple[list[str], str]:
    cfg = load_yaml(path)
    logs = cfg.get("logs", []) or []
    output_dir = cfg.get("output_dir", "output")
    return logs, output_dir


def load_rules(path: str) -> dict:
    cfg = load_yaml(path)
    return cfg.get("categories", {}) or {}


def _compile(cat_cfg: dict):
    patterns = [p.lower() for p in cat_cfg.get("patterns", []) or []]
    regexes = []
    for r in cat_cfg.get("regex", []) or []:
        try:
            regexes.append(re.compile(r, re.IGNORECASE))
        except re.error:
            pass
    return patterns, regexes


def classify_line(line: str, rules: dict) -> list[str]:
    low = line.lower()
    matched = []
    for category, cat_cfg in rules.items():
        patterns, regexes = _compile(cat_cfg)
        hit = any(p in low for p in patterns) or any(r.search(line) for r in regexes)
        if hit:
            matched.append(category)
    return matched


def sort_logs(input_paths: list[str], output_dir: str, rules: dict) -> dict:
    os.makedirs(output_dir, exist_ok=True)
    writers = {}
    stats = {cat: 0 for cat in rules}
    stats["unmatched"] = 0

    def get_writer(cat: str):
        if cat not in writers:
            writers[cat] = open(
                os.path.join(output_dir, f"{cat}.log"), "w", encoding="utf-8"
            )
        return writers[cat]

    for path in input_paths:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                cats = classify_line(line, rules) or ["unmatched"]
                for cat in cats:
                    stats[cat] += 1
                    get_writer(cat).write(line)

    for w in writers.values():
        w.close()
    return stats

class StreamSorter:
    """Инкрементальная сортировка: пишет по строке, держит файлы открытыми."""

    def __init__(self, output_dir: str, rules: dict):
        self.output_dir = output_dir
        self.rules = rules
        self.writers = {}
        self.stats = {cat: 0 for cat in rules}
        self.stats["unmatched"] = 0
        os.makedirs(output_dir, exist_ok=True)

    def _writer(self, cat: str):
        if cat not in self.writers:
            self.writers[cat] = open(
                os.path.join(self.output_dir, f"{cat}.log"),
                "a", encoding="utf-8",
            )
        return self.writers[cat]

    def feed(self, line: str):
        cats = classify_line(line, self.rules) or ["unmatched"]
        for cat in cats:
            self.stats[cat] += 1
            self._writer(cat).write(line)
            self._writer(cat).flush()

    def close(self):
        for w in self.writers.values():
            w.close()
