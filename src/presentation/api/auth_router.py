from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from src.application.services.auth import AuthService, get_current_user
from src.infrastructure.database.models import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/login")
async def login(request: Request):
    """Endpoint para iniciar sesión"""
    data = await request.json()
    
    if not data or not data.get('username') or not data.get('password'):
        raise HTTPException(status_code=400, detail="Se requiere usuario y contraseña")
        
    session_data, error = AuthService.authenticate_user(
        data['username'],
        data['password'],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", "")
    )
    
    if error:
        raise HTTPException(status_code=401, detail=error)
    
    return {
        "success": True,
        "message": "Autenticación exitosa",
        "data": session_data
    }

@router.get("/me")
async def verify_session(request: Request, user: User = Depends(get_current_user)):
    """
    Ruta protegida para validar si un token sigue siendo válido
    y obtener los datos del usuario actual.
    """
    return {
        "success": True,
        "data": user.to_dict(),
        "tenant": {
            "id": getattr(request.state, "tenant_id", None),
            "name": getattr(request.state, "tenant_name", "SGUBM"),
            "brand_color": getattr(request.state, "brand_color", "#4f46e5"),
            "logo_path": getattr(request.state, "logo_path", None)
        }
    }

@router.post("/logout")
async def logout(request: Request):
    """Destruye una sesión activa"""
    auth_header = request.headers.get('Authorization')
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        AuthService.logout(token)
        
    return {
        "success": True,
        "message": "Sesión cerrada correctamente"
    }
