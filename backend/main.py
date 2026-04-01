from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client, Client
import os
import io
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME  = "archivos"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI(title="R1K0VxNEBULA Drive API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # En producción pon tu dominio real
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    user_email: str


# ── Helper: obtener usuario desde token ────────────────────────────────────────

def get_current_user(authorization: str = None):
    """Extrae el access_token del header Authorization: Bearer <token>"""
    from fastapi import Header
    return authorization


def require_auth(authorization: str = Depends(
    lambda authorization: authorization  # se pasa via header
)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    return authorization.split(" ")[1]


# ── Rutas ──────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "R1K0VxNEBULA Drive activo 🚀"}


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """Inicia sesión con email y contraseña (usuarios de Supabase Auth)."""
    try:
        res = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
        return LoginResponse(
            access_token=res.session.access_token,
            user_email=res.user.email
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")


@app.post("/auth/logout")
def logout(token: str = Depends(require_auth)):
    supabase.auth.sign_out()
    return {"message": "Sesión cerrada"}


@app.get("/files")
def list_files(token: str = Depends(require_auth)):
    """Lista todos los archivos del usuario autenticado."""
    # Usar el token del usuario para consultar solo sus archivos
    user_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    user_client.postgrest.auth(token)

    try:
        # Obtener info del usuario
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        # Listar archivos en la carpeta del usuario dentro del bucket
        res = supabase.storage.from_(BUCKET_NAME).list(path=user_id)
        files = []
        for f in res:
            if f.get("name"):
                files.append({
                    "name": f["name"],
                    "size": f.get("metadata", {}).get("size", 0),
                    "created_at": f.get("created_at", ""),
                    "path": f"{user_id}/{f['name']}"
                })
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    token: str = Depends(require_auth)
):
    """Sube un archivo al bucket del usuario."""
    try:
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        contents = await file.read()
        path = f"{user_id}/{file.filename}"

        supabase.storage.from_(BUCKET_NAME).upload(
            path=path,
            file=contents,
            file_options={"content-type": file.content_type or "application/octet-stream"}
        )

        return {"message": "Archivo subido", "path": path, "name": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/download/{filename}")
def download_file(filename: str, token: str = Depends(require_auth)):
    """Descarga un archivo del bucket del usuario."""
    try:
        user = supabase.auth.get_user(token)
        user_id = user.user.id
        path = f"{user_id}/{filename}"

        data = supabase.storage.from_(BUCKET_NAME).download(path)

        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")


@app.delete("/files/{filename}")
def delete_file(filename: str, token: str = Depends(require_auth)):
    """Elimina un archivo del bucket del usuario."""
    try:
        user = supabase.auth.get_user(token)
        user_id = user.user.id
        path = f"{user_id}/{filename}"

        supabase.storage.from_(BUCKET_NAME).remove([path])
        return {"message": f"'{filename}' eliminado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
