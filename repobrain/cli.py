import argparse
import json
from pathlib import Path
import shutil
import subprocess

from .store import default_store


def main():
    parser = argparse.ArgumentParser(description="RepoBrain local code intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    index = sub.add_parser("index")
    index.add_argument("path")
    sub.add_parser("demo")
    sub.add_parser("mcp")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("benchmark")
    evaluate.add_argument("--repo", type=int, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        uvicorn.run("repobrain.app:create_app", factory=True, host="127.0.0.1", port=args.port)
    elif args.command == "mcp":
        from .mcp_server import run
        run()
    elif args.command == "index":
        print(json.dumps(default_store().index(args.path), indent=2))
    elif args.command == "demo":
        store = default_store()
        destination = store.location.parent / "demo-shop"
        if not destination.exists():
            sample = Path(__file__).resolve().parent.parent / "examples" / "shop"
            shutil.copytree(sample, destination)
            for command in [["init"], ["add", "."], ["-c", "user.name=RepoBrain Demo", "-c", "user.email=demo@localhost", "commit", "-m", "Add demo shop"]]:
                subprocess.run(["git", "-C", str(destination), *command], check=True, capture_output=True)
        print(json.dumps(store.index(destination), indent=2))
    elif args.command == "eval":
        store = default_store()
        benchmark = json.loads(Path(args.benchmark).read_text())
        results = []
        for case in benchmark:
            hits = store.search(args.repo, case["question"], 5)
            found = {f'{hit["path"]}:{hit["symbol"]}' for hit in hits}
            expected = set(case["expected"])
            results.append({"question": case["question"], "recall_at_5": len(found & expected) / len(expected), "retrieved": sorted(found)})
        print(json.dumps({"cases": results, "mean_recall_at_5": sum(r["recall_at_5"] for r in results) / len(results)}, indent=2))


if __name__ == "__main__":
    main()
