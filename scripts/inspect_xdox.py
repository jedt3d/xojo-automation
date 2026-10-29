#!/usr/bin/env python3
"""Read XDOX index/model readiness without modifying its database or notes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import urllib.request


def inspect(data_dir):
    result = {"timestamp": datetime.now(timezone.utc).isoformat(),
              "dataDirectory": str(data_dir)}
    database = data_dir / "xdox.db"
    try:
        with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            result["counts"] = [
                {"version": version, "chunks": count, "embedded": embedded}
                for version, count, embedded in connection.execute(
                    "select docs_version,count(*),sum(embedded) from chunks group by docs_version")]
            result["metadata"] = dict(connection.execute("select * from metadata"))
            result["allChunksEmbedded"] = bool(result["counts"]) and all(
                row["chunks"] == row["embedded"] for row in result["counts"])
    except sqlite3.Error as error:
        result["databaseError"] = str(error)
    models = data_dir / "models"
    result["models"] = [{"name": path.name, "bytes": path.stat().st_size}
                        for path in sorted(models.glob("*.gguf*")) if path.is_file()]
    for name, port in [("embeddingService", 8089), ("rerankerService", 8093)]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                result[name] = {"status": response.status,
                                "body": response.read(1024).decode(errors="replace")}
        except OSError as error:
            result[name] = {"error": str(error)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path,
                        default=Path.home() / "Library/Application Support/dk.o3jvind.xdox")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(inspect(args.data_dir), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
