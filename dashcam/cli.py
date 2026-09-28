import argparse
import json
import sys

from . import __version__
from . import bootstrap, demo
from .server import DEFAULT_PORT, serve
from .storage import Store


def _store(args):
    return Store(getattr(args, "db", None) or None)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="dashcam",
        description="The dashcam for your AI agents - local tracing, replay and cost debugging")
    parser.add_argument("--version", action="version", version=f"dashcam {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_serve = sub.add_parser("serve", help="launch the dashboard (default)")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.add_argument("--no-open", action="store_true")
    p_serve.add_argument("--db")

    p_demo = sub.add_parser("demo", help="generate demo traces, no API key needed")
    p_demo.add_argument("--db")

    sub.add_parser("install", help="enable zero-code auto-instrumentation (.pth hook)")
    sub.add_parser("uninstall", help="disable auto-instrumentation")

    p_export = sub.add_parser("export", help="export one trace as JSON")
    p_export.add_argument("trace_id")
    p_export.add_argument("--db")

    sub.add_parser("clear", help="delete all recorded traces")

    args = parser.parse_args(argv)
    cmd = args.cmd or "serve"

    if cmd == "serve":
        serve(_store(args), port=args.port, open_browser=not args.no_open)
    elif cmd == "demo":
        n = demo.run(_store(args))
        print(f"generated {n} demo traces")
        print("run `dashcam` to open the dashboard")
    elif cmd == "install":
        path = bootstrap.install()
        print(f"installed: {path}")
        print("now run your agent with:  DASHCAM=1 python your_agent.py")
        print("(on Windows:  set DASHCAM=1 && python your_agent.py)")
    elif cmd == "uninstall":
        path = bootstrap.uninstall()
        print("removed" if path else "not installed")
    elif cmd == "export":
        data = _store(args).get_trace(args.trace_id)
        if data is None:
            print(f"trace not found: {args.trace_id}", file=sys.stderr)
            return 1
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2, default=str)
    elif cmd == "clear":
        _store(args).clear()
        print("all traces deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
