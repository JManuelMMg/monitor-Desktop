"""Páginas HTML (Jinja2). Toda la lógica de datos va por la API."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import BASE_DIR
from ..deps import optional_user
from ..security import has_role
from ..topics import normalize_mac

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _render(request: Request, name: str, user: dict | None, **context) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name=name, context={"user": user, **context})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if optional_user(request):
        return RedirectResponse("/", status_code=303)
    return _render(request, "login.html", None)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = optional_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "dashboard.html", user, page="dashboard")


@router.get("/nodes/{mac}", response_class=HTMLResponse)
def node_page(request: Request, mac: str):
    user = optional_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    normalized = normalize_mac(mac)
    if not normalized:
        return RedirectResponse("/", status_code=303)
    return _render(request, "node.html", user, page="node", mac=normalized,
                   can_operate=has_role(user["role"], "operator"),
                   is_admin=has_role(user["role"], "admin"))


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    user = optional_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not has_role(user["role"], "admin"):
        return RedirectResponse("/", status_code=303)
    return _render(request, "admin.html", user, page="admin")


@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    user = optional_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "account.html", user, page="account")


@router.get("/connection", response_class=HTMLResponse)
def connection_page(request: Request):
    user = optional_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "connection.html", user, page="connection")


# ---------------------------------------------------------------- app web
# Estas rutas son públicas: el navegador las pide antes de iniciar sesión
# (manifiesto e instalación) o cuando el servidor no responde (página offline).

@router.get("/offline", response_class=HTMLResponse)
def offline_page(request: Request):
    return _render(request, "offline.html", None)


@router.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name": "Monitor multi-nodo",
        "short_name": "Monitor",
        "description": "Monitoreo en vivo de biodigestores con nodos ESP32",
        "lang": "es",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#070b10",
        "theme_color": "#0f1720",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Panel general", "url": "/"},
            {"name": "Conexión", "url": "/connection"},
        ],
    }, media_type="application/manifest+json")


@router.get("/sw.js")
def service_worker():
    # Servido desde la raíz para que su alcance sea todo el sitio.
    return FileResponse(BASE_DIR / "static" / "js" / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})
