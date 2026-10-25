import argparse
import os
from datetime import datetime
from sorter import load_paths, load_rules, sort_logs, StreamSorter

C_RESET = "\033[0m"
C_DIM = "\033[2m"
C_BOLD = "\033[1m"
C_CAT = {
    "users": "\033[94m",
    "config": "\033[92m",
    "network": "\033[96m",
    "errors": "\033[91m",
    "cron": "\033[93m",
    "unmatched": "\033[90m",
}


def c(text: str, color: str = "") -> str:
    return f"{color}{text}{C_RESET}" if color else text


def print_stats(stats: dict, title: str = ""):
    total = sum(stats.values())
    if title:
        print(f"  {c(title, C_BOLD)}")
    print(f"  {c('lines', C_DIM)}  {total}")
    width = max((len(k) for k in stats), default=0)
    for cat, count in stats.items():
        color = C_CAT.get(cat, "")
        bar = "·" * min(count, 40)
        print(f"    {c(cat.ljust(width), color)}  {str(count).rjust(4)}  {c(bar, C_DIM)}")
    print()


def run_follow(input_paths, output_dir, rules):
    from tailer import LogTailer

    sorter = StreamSorter(output_dir, rules)

    def on_line(line: str):
        sorter.feed(line)
        low = line.lower().rstrip()
        cats = [k for k in sorter.stats if k != "unmatched"
                and any(p in low for p in
                        [x.lower() for x in rules.get(k, {}).get("patterns", [])])]
        if not cats:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        tag = c(",".join(cats).ljust(22), C_BOLD)
        print(f"  {c(ts, C_DIM)}  {tag}  {line.rstrip()}")

    print()
    print(f"  {c('log-sorter', C_BOLD)}  {c('live', C_DIM)}")
    for p in input_paths:
        mark = c("●", "\033[92m") if os.path.isfile(p) else c("○", "\033[90m")
        print(f"    {mark}  {p}")
    print(f"    {c('→', C_DIM)}  {output_dir}")
    print(f"  {c('Ctrl+C', C_DIM)} — stop")
    print()

    try:
        LogTailer(input_paths, on_line).start()
    except KeyboardInterrupt:
        pass
    finally:
        sorter.close()
        print_stats(sorter.stats, "session")


def main():
    parser = argparse.ArgumentParser(description="Сортировка логов по категориям")
    parser.add_argument("-p", "--paths", default="config/paths.yaml",
                        help="Конфиг с путями к логам")
    parser.add_argument("-r", "--rules", default="config/rules.yaml",
                        help="Конфиг с правилами")
    parser.add_argument("-o", "--output", default=None,
                        help="Переопределить output_dir из конфига")
    parser.add_argument("-f", "--follow", action="store_true",
                        help="Следить за логами в реальном времени")
    args = parser.parse_args()

    input_paths, output_dir = load_paths(args.paths)
    if args.output:
        output_dir = args.output

    rules = load_rules(args.rules)

    if args.follow:
        run_follow(input_paths, output_dir, rules)
        return

    stats = sort_logs(input_paths, output_dir, rules)

    print()
    print(f"  {c('log-sorter', C_BOLD)}  {c('scan', C_DIM)}")
    for p in input_paths:
        mark = c("●", "\033[92m") if os.path.isfile(p) else c("○", "\033[90m")
        print(f"    {mark}  {p}")
    print(f"    {c('→', C_DIM)}  {output_dir}")
    print()
    print_stats(stats)
    summary_path = os.path.join(output_dir, "summary.txt")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"total: {sum(stats.values())}\n")
        for cat, count in stats.items():
            f.write(f"{cat}: {count}\n")
    print(f"  {c('summary', C_DIM)}  {summary_path}")
    print()


if __name__ == "__main__":
    main()
