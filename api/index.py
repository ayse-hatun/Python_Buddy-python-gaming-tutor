import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from main import app as fastapi_app
from starlette.types import ASGIApp, Scope, Receive, Send


class VercelPathFixer:
    """Restores the original /api/* route path when rewritten by Vercel."""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http":
            query_string = scope.get("query_string", b"").decode("utf-8")
            params = parse_qs(query_string, keep_blank_values=True)
            if "__path__" in params:
                subpath = params.pop("__path__")[0].lstrip("/")
                new_path = f"/api/{subpath}"
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("utf-8")
                # Re-encode remaining query parameters
                pairs = []
                for k, vals in params.items():
                    for v in vals:
                        pairs.append((k, v))
                scope["query_string"] = urlencode(pairs).encode("utf-8")
        await self.app(scope, receive, send)


app = VercelPathFixer(fastapi_app)
