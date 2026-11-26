"""Envio do e-mail com o código de recuperação de senha.

Sai pela API do Brevo ou por SMTP com SSL, conforme EMAIL_PROVEDOR
(ver core/integracoes.py). O SMTP usa a mesma configuração do e-mail do código
de login (SMTP_HOST, SMTP_PORT, SMTP_EMAIL e SMTP_SENHA_APP).
"""

import smtplib
from email.message import EmailMessage

from core.integracoes import PROVEDOR_BREVO, email_provedor
from core.parametros import smtp_email, smtp_host, smtp_porta, smtp_senha_app
from services.brevo import enviar_pelo_brevo

ASSUNTO = "Recuperação de senha - SimpleMark"

# Sem prazo, um servidor de e-mail que não responde prenderia o pedido para sempre.
TIMEOUT_SMTP_SEGUNDOS = 15


def enviar_codigo_recuperacao(destinatario: str, codigo: str, validade_minutos: int) -> None:
    """Manda o código de recuperação de senha ao destinatário pelo provedor configurado.

    Erros de conexão e de envio sobem para quem chama.

    Args:
        destinatario (str): E-mail que recebe o código.
        codigo (str): Código de recuperação.
        validade_minutos (int): Validade do código, em minutos, citada no texto.

    Raises:
        ErroBrevo: Quando o envio pelo Brevo falha ou não está configurado.
        RuntimeError: Quando o remetente ou a senha de app do SMTP não estão configurados.
    """
    texto = f"""Olá!

Recebemos um pedido para redefinir a senha da sua conta no SimpleMark.

Seu código de recuperação é: {codigo}

Ele é válido por {validade_minutos} minutos e pode ser utilizado apenas uma vez.

Se você não pediu a redefinição, ignore este e-mail: sua senha continua a mesma.
"""
    if email_provedor() == PROVEDOR_BREVO:
        enviar_pelo_brevo(destinatario, ASSUNTO, texto)
        return
    _enviar_por_smtp(destinatario, texto)


def _enviar_por_smtp(destinatario: str, texto: str) -> None:
    """Envia o código por SMTP com SSL.

    Args:
        destinatario (str): E-mail que recebe o código.
        texto (str): Corpo da mensagem.

    Raises:
        RuntimeError: Quando o remetente ou a senha de app não estão configurados.
    """
    remetente = smtp_email()
    senha_app = smtp_senha_app()

    if not remetente or not senha_app:
        raise RuntimeError("As configurações de envio de e-mail não foram definidas.")

    mensagem = EmailMessage()
    mensagem["Subject"] = ASSUNTO
    mensagem["From"] = remetente
    mensagem["To"] = destinatario
    mensagem.set_content(texto)

    with smtplib.SMTP_SSL(smtp_host(), smtp_porta(), timeout=TIMEOUT_SMTP_SEGUNDOS) as servidor:
        servidor.login(remetente, senha_app)
        servidor.send_message(mensagem)
