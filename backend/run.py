"""Development server entrypoint for the Tranquilytics API.

``uvicorn ... --reload`` starts a WatchFiles *supervisor* that ``spawn``s workers and wraps
``Server.run()`` in ``except KeyboardInterrupt: pass``. On CPython 3.14 that pattern can surface::

    RuntimeWarning: coroutine 'Server.serve' was never awaited

This script avoids uvicorn's multiprocessing reload path:

- Default: single-process ``uvicorn.run(..., reload=False)``
- ``--reload``: restart via ``watchfiles.run_process`` (already pulled in by ``uvicorn[standard]``),
  still running plain uvicorn without ``reload=True``.
"""

from __future__ import annotations

import argparse
import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_IMPORT = "app.main:app"


def _serve_uvicorn(host: str, port: int) -> None:
    os.chdir(BACKEND_ROOT)
    if BACKEND_ROOT not in sys.path:
        sys.path.insert(0, BACKEND_ROOT)

    import uvicorn

    uvicorn.run(APP_IMPORT, host=host, port=port, reload=False, factory=False)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(description="Tranquilytics API dev server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart on Python changes under app/ (watchfiles; avoids uvicorn --reload subprocess)",
    )
    args = parser.parse_args(argv)

    if args.reload:
        try:
            from watchfiles import run_process
            from watchfiles.filters import PythonFilter
        except ImportError as e:
            raise SystemExit(
                "watchfiles is required for --reload. Install backend deps: pip install -r requirements.txt"
            ) from e

        watch_root = os.path.join(BACKEND_ROOT, "app")
        run_process(
            watch_root,
            target=_serve_uvicorn,
            args=(args.host, args.port),
            watch_filter=PythonFilter(),
        )
        return

    _serve_uvicorn(args.host, args.port)


if __name__ == "__main__":
    main()
