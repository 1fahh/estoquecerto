from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAIZ_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(RAIZ_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    jwt_expire_days: int = 7

    admin_email: str | None = None
    admin_password: str | None = None
    admin_nome: str = "Administradora"

    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    alert_email_to: str | None = None

    app_url: str = "http://localhost:8000"
    static_dir: str = "static"

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_obrigatorio(cls, valor: str) -> str:
        if not valor.strip():
            raise ValueError("JWT_SECRET é obrigatória: configure a variável de ambiente.")
        return valor

    @field_validator("database_url")
    @classmethod
    def normalizar_database_url(cls, valor: str) -> str:
        partes = urlsplit(valor)
        esquema = partes.scheme
        if esquema in ("postgres", "postgresql"):
            esquema = "postgresql+psycopg"
        consulta = [
            (chave, valor_consulta)
            for chave, valor_consulta in parse_qsl(partes.query, keep_blank_values=True)
            if chave != "channel_binding"
        ]
        return urlunsplit((esquema, partes.netloc, partes.path, urlencode(consulta), partes.fragment))

    @property
    def static_path(self) -> Path:
        caminho = Path(self.static_dir)
        return caminho if caminho.is_absolute() else BACKEND_DIR / caminho


@lru_cache
def get_settings() -> Settings:
    return Settings()
