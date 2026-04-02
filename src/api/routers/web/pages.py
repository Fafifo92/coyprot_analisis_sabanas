from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="templates/web")

def render_template(request: Request, name: str, context: dict = None):
    """
    Renderiza una plantilla lidiando automáticamente con las diferencias
    de API entre las distintas versiones de FastAPI y Starlette.
    """
    ctx = context or {}
    ctx["request"] = request

    try:
        # Intenta sintaxis moderna (FastAPI > 0.108 / Starlette >= 0.28)
        return templates.TemplateResponse(request=request, name=name, context=ctx)
    except TypeError:
        # Fallback a la sintaxis antigua posicional (FastAPI <= 0.108)
        return templates.TemplateResponse(name, ctx)

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(request, "login.html")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return render_template(request, "dashboard.html")

@router.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    return render_template(request, "users.html")

@router.get("/admin/projects", response_class=HTMLResponse)
async def admin_projects_page(request: Request):
    return render_template(request, "admin_projects.html")

@router.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit_page(request: Request):
    return render_template(request, "admin_audit.html")

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return render_template(request, "settings.html")

@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail_page(request: Request, project_id: int):
    return render_template(request, "project_detail.html", {"project_id": project_id})

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return render_template(request, "login.html")
