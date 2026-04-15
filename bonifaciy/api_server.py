from __future__ import annotations

import io
import json
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

from .auth import authenticate_token, issue_token
from .db import managed_connection
from .migrations import MIGRATIONS, run_migrations
from .ops import log_operation
from .rbac import has_permission


def _json(start_response, status: str, payload: dict | list):
    start_response(status, [("Content-Type", "application/json")])
    return [json.dumps(payload, ensure_ascii=False).encode("utf-8")]


def _read_json(environ) -> dict:
    size = int(environ.get("CONTENT_LENGTH", "0") or 0)
    body = environ["wsgi.input"].read(size) if size > 0 else b"{}"
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return {}


def _extract_bearer(environ) -> str | None:
    auth = environ.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.split(" ", 1)[1].strip()


def create_app(db_path):
    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")

        with managed_connection(db_path) as conn:
            run_migrations(conn)

            if path == "/health" and method == "GET":
                body = {"status": "ok", "schema_version": len(MIGRATIONS)}
                return _json(start_response, "200 OK", body)

            if path == "/auth/login" and method == "POST":
                payload = _read_json(environ)
                token = issue_token(conn, payload.get("login", ""), payload.get("password", ""))
                if not token:
                    return _json(start_response, "401 Unauthorized", {"error": "invalid_credentials"})
                log_operation(conn, "api-auth", "auth.login", "INFO", f"login={payload.get('login', '')}")
                return _json(start_response, "200 OK", {"token": token})

            if path == "/ui" and method == "GET":
                page = """
                <html><body><h1>Bonifaciy API UI</h1>
                <p>Use /auth/login to get bearer token, then call /projects and /mail/outbox.</p>
                </body></html>
                """
                start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
                return [page.encode("utf-8")]

            token = _extract_bearer(environ)
            user = authenticate_token(conn, token) if token else None
            if user is None:
                return _json(start_response, "401 Unauthorized", {"error": "unauthorized"})

            if path == "/projects" and method == "GET":
                if not has_permission(conn, user.role, "projects.read"):
                    return _json(start_response, "403 Forbidden", {"error": "forbidden"})

                if user.role == "administrator":
                    rows = conn.execute(
                        "SELECT id, name, status, archived FROM projects ORDER BY id DESC LIMIT 200"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT p.id, p.name, p.status, p.archived
                        FROM projects p
                        LEFT JOIN project_members pm ON pm.project_id = p.id
                        WHERE p.owner_user_id = ? OR pm.user_id = ?
                        ORDER BY p.id DESC
                        LIMIT 200
                        """,
                        (user.user_id, user.user_id),
                    ).fetchall()
                return _json(start_response, "200 OK", [dict(r) for r in rows])

            if path == "/mail/outbox" and method == "GET":
                if not has_permission(conn, user.role, "mail.read"):
                    return _json(start_response, "403 Forbidden", {"error": "forbidden"})
                rows = conn.execute(
                    """
                    SELECT mo.id, mo.account_id, mo.recipient, mo.subject, mo.state, mo.attempts
                    FROM mail_outbox mo
                    JOIN mail_accounts ma ON ma.id = mo.account_id
                    WHERE ma.user_id = ? OR ? = 'administrator'
                    ORDER BY mo.id DESC LIMIT 200
                    """,
                    (user.user_id, user.role),
                ).fetchall()
                return _json(start_response, "200 OK", [dict(r) for r in rows])

        return _json(start_response, "404 Not Found", {"error": "not_found"})

    return app


def run_api_server(db_path, host="0.0.0.0", port=8080):
    app = create_app(db_path)
    server = make_server(host, port, app)
    server.serve_forever()
