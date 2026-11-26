import logging
import smtplib
from decimal import Decimal
from email.message import EmailMessage

from app.config import get_settings
from app.models import Alerta, Produto

logger = logging.getLogger(__name__)
TIMEOUT_SMTP_SEGUNDOS = 15


def _quantidade(valor: Decimal) -> str:
    return format(valor.normalize(), "f").replace(".", ",")


def _corpo(produto: Produto, saldo: Decimal, limite: Decimal, link: str) -> str:
    unidade = produto.unidade
    return (
        f"O produto {produto.nome} atingiu o limite de reposição.\n\n"
        f"Saldo atual: {_quantidade(saldo)} {unidade}\n"
        f"Limite de reposição: {_quantidade(limite)} {unidade}\n\n"
        f"Veja o produto: {link}\n\n"
        "— EstoqueCerto"
    )


def enviar_alerta(
    alerta: Alerta,
    produto: Produto,
    saldo: Decimal,
    limite: Decimal,
    destinatario: str | None = None,
) -> bool:
    settings = get_settings()
    assunto = f"[EstoqueCerto] Repor: {produto.nome}"
    link = f"{settings.app_url.rstrip('/')}/produtos/{produto.id}"
    para = settings.alert_email_to or destinatario

    if not settings.email_enabled:
        logger.info("E-mail desativado; alerta %s (%s) não enviado.", assunto, para or "sem destinatário")
        return False
    if not (settings.smtp_host and settings.smtp_from and para):
        logger.warning("E-mail não enviado: SMTP ou destinatário não configurado (alerta %s).", alerta.id)
        return False

    try:
        # Montar a mensagem também fica no try: um nome com quebra de linha não pode derrubar a operação.
        mensagem = EmailMessage()
        mensagem["Subject"] = assunto
        mensagem["From"] = settings.smtp_from
        mensagem["To"] = para
        mensagem.set_content(_corpo(produto, saldo, limite, link))
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SMTP_SEGUNDOS) as smtp:
            smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(mensagem)
    except Exception:
        logger.exception("Falha ao enviar e-mail do alerta %s.", alerta.id)
        return False
    logger.info("E-mail de alerta enviado para o produto %s.", produto.id)
    return True
