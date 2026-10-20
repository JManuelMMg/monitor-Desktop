from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..config import settings
from ..deps import viewer

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/connection")
def connection_info(request: Request, _: dict = Depends(viewer)):
    """Direcciones conocidas de este servidor, para la conmutación LAN ↔ VPN."""
    current = f"{request.url.scheme}://{request.url.netloc}"
    urls = list(settings.public_urls)
    if current not in urls:
        urls.insert(0, current)
    return {"current": current, "urls": urls}
