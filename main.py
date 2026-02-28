import os
import logging
from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import socketio

from src.infrastructure.config.settings import get_config
from src.application.events.event_bus import get_event_bus, SystemEvents
from src.presentation.api.websocket_events import register_socket_events
from src.application.services.automation_manager import AutomationManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = get_config()

# Create FastAPI app
app = FastAPI(
    title="SGUBM-V1 API",
    description="Sistema de Gestión ISP - Personalizado",
    version="2.0.0",
    debug=config.system.debug_mode
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
app.mount("/static", StaticFiles(directory="src/presentation/web/static"), name="static")

# Templates
templates = Jinja2Templates(directory="src/presentation/web/templates")

# Import and Register Routers
from src.presentation.api.auth_router import router as auth_router
from src.presentation.api.payments_router import router as payments_router
from src.presentation.api.clients_router import router as clients_router
from src.presentation.api.routers_router import router as routers_router
from src.presentation.api.dashboard_router import router as dashboard_router
from src.presentation.api.users_router import router as users_router
from src.presentation.api.sync_router import router as sync_router
from src.presentation.api.whatsapp_router import router as whatsapp_router
from src.presentation.api.billing_router import router as billing_router
from src.presentation.api.plans_router import router as plans_router
from src.presentation.api.reports_router import router as reports_router
app.include_router(auth_router)
app.include_router(payments_router)
app.include_router(clients_router)
app.include_router(routers_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(sync_router)
app.include_router(whatsapp_router)
app.include_router(billing_router)
app.include_router(plans_router)
app.include_router(reports_router)

# Socket.io transition (Async ASGI)
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio, app)

# Register Events & Start Background Services
register_socket_events(sio)
AutomationManager.get_instance().start()

# Global Dependency: Resolve Tenant
async def resolve_tenant(request: Request):
    from src.application.services.tenant_service import TenantService
    host = request.headers.get("host", "")
    tenant = TenantService.resolve_from_host(host)
    if tenant:
        # En FastAPI, inyectamos en el estado de la petición
        request.state.tenant_id = tenant.id
        request.state.tenant_name = tenant.name
        request.state.brand_color = tenant.brand_color
        request.state.logo_path = tenant.logo_path
    return tenant

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, tenant=Depends(resolve_tenant)):
    """Sirve la Single Page Application"""
    # Contexto global para Jinja2 (emulando el objeto 'g' de Flask)
    context = {
        "request": request,
        "g": request.state if hasattr(request.state, "tenant_id") else type('obj', (object,), {'brand_color': '#4f46e5', 'tenant_name': 'SGUB Pro'})()
    }
    return templates.TemplateResponse("index.html", context)

# Errores SPA: Redirigir 404 a index si no es API
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Resource not found"}
        )
    return await index(request)

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting SGUBM-V1 with FastAPI...")
    uvicorn.run(socket_app, host="0.0.0.0", port=8000)
