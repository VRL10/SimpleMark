"""Envio do e-mail com o código de confirmação do login.

Sai pela API do Brevo ou por SMTP com SSL, conforme EMAIL_PROVEDOR
(ver core/integracoes.py).
"""

import smtplib
from email.message import EmailMessage

from core.integracoes import PROVEDOR_BREVO, email_provedor
from core.parametros import (
    codigo_login_validade_minutos,
    smtp_email,
    smtp_host,
    smtp_porta,
    smtp_senha_app,
)
from services.brevo import enviar_pelo_brevo

ASSUNTO = "Código de confirmação - SimpleMark"

# Sem prazo, um servidor de e-mail que não responde prenderia o login para sempre.
TIMEOUT_SMTP_SEGUNDOS = 15


def enviar_codigo_login(destinatario: str, codigo: str) -> None:
    """Manda o código de login ao destinatário pelo provedor configurado.

    Erros de conexão e de envio sobem para quem chama.

    Args:
        destinatario (str): E-mail que recebe o código.
        codigo (str): Código de confirmação do login.

    Raises:
        ErroBrevo: Quando o envio pelo Brevo falha ou não está configurado.
        RuntimeError: Quando o remetente ou a senha de app do SMTP não estão configurados.
    """
    texto = f"""Olá!

Seu código de confirmação de login no SimpleMark é: {codigo}

Ele é válido por {codigo_login_validade_minutos()} minutos e pode ser utilizado apenas uma vez.

Se você não tentou entrar na sua conta, ignore este e-mail.
"""
    if email_provedor() == PROVEDOR_BREVO:
        enviar_pelo_brevo(destinatario, ASSUNTO, texto)
        return
    _enviar_por_smtp(destinatario, texto)


def _enviar_por_smtp(destinatario: str, texto: str) -> None:
    """Envia o código por SMTP com SSL (SMTP_HOST, SMTP_PORT, SMTP_EMAIL, SMTP_SENHA_APP).

    Args:
        destinatario (str): E-mail que recebe o código.
        texto (str): Corpo da mensagem.

    Raises:
        RuntimeError: Quando o remetente ou a senha de app não estão configurados.
    """
    remetente = smtp_email()
    senha_app = smtp_senha_app()

    if not remetente or not senha_app:
        raise RuntimeError(
            "As configurações de envio de e-mail não foram definidas."
        )

    mensagem = EmailMessage()
    mensagem["Subject"] = ASSUNTO
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto)

    with smtplib.SMTP_SSL(smtp_host(), smtp_porta(), timeout=TIMEOUT_SMTP_SEGUNDOS) as servidor:
        servidor.login(remetente, senha_app)
        servidor.send_message(mensagem)
