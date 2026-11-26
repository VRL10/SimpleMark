"""Envio de e-mail transacional pela API HTTP do Brevo (POST /v3/smtp/email).

Usado em produção no lugar do SMTP: a API sai pela porta 443 (HTTPS), que os
provedores de hospedagem não bloqueiam. A configuração vem de core/integracoes.py
(BREVO_API_KEY, EMAIL_REMETENTE e EMAIL_REMETENTE_NOME).

A chave da API nunca aparece em log nem na mensagem de erro.
"""

from html import escape

import httpx

from core.integracoes import brevo_api_key, brevo_api_url, email_remetente, email_remetente_nome

# Sem prazo, uma API que não responde prenderia a requisição para sempre.
TIMEOUT_BREVO_SEGUNDOS = 15


class ErroBrevo(Exception):
    """Falha ao enviar pelo Brevo. A mensagem não traz a chave nem o conteúdo do e-mail."""


def texto_para_html(texto: str) -> str:
    """Converte texto puro em HTML simples, um parágrafo por bloco.

    A API do Brevo exige ``htmlContent`` quando não se usa template.

    Args:
        texto (str): Corpo do e-mail em texto puro.

    Returns:
        str: O mesmo conteúdo em HTML, com o texto escapado.
    """
    blocos = [bloco.strip() for bloco in texto.split("\n\n") if bloco.strip()]
    return "".join(f"<p>{escape(bloco).replace(chr(10), '<br>')}</p>" for bloco in blocos)


def enviar_pelo_brevo(destinatario: str, assunto: str, texto: str, html: str | None = None) -> None:
    """Envia um e-mail pela API do Brevo.

    Args:
        destinatario (str): E-mail de destino.
        assunto (str): Assunto da mensagem.
        texto (str): Corpo em texto puro.
        html (str | None): Corpo em HTML. Sem ele, o HTML é gerado a partir do texto.

    Raises:
        ErroBrevo: Quando a chave ou o remetente não estão configurados, quando a
            API não responde ou quando ela recusa o envio.
    """
    chave = brevo_api_key()
    remetente = email_remetente()
    if not chave or not remetente:
        raise ErroBrevo("Envio pelo Brevo não configurado (BREVO_API_KEY e EMAIL_REMETENTE).")

    corpo = {
        "sender": {"name": email_remetente_nome(), "email": remetente},
        "to": [{"email": destinatario}],
        "subject": assunto,
        "textContent": texto,
        "htmlContent": html or texto_para_html(texto),
    }
    cabecalhos = {"api-key": chave, "accept": "application/json", "content-type": "application/json"}

    try:
        resposta = httpx.post(brevo_api_url(), json=corpo, headers=cabecalhos, timeout=TIMEOUT_BREVO_SEGUNDOS)
    except httpx.HTTPError as exc:
        raise ErroBrevo(f"Falha ao conectar ao Brevo ({type(exc).__name__}).") from exc

    if not resposta.is_success:
        raise ErroBrevo(f"O Brevo recusou o envio (HTTP {resposta.status_code}, {_codigo_erro(resposta)}).")


def _codigo_erro(resposta: httpx.Response) -> str:
    """Código de erro devolvido pelo Brevo (ex.: ``unauthorized``), sem o texto completo.

    Args:
        resposta (httpx.Response): Resposta de erro da API.

    Returns:
        str: Código do erro, ou ``"sem código"`` quando a resposta não traz um.
    """
    try:
        dados = resposta.json()
    except ValueError:
        return "sem código"
    codigo = dados.get("code") if isinstance(dados, dict) else None
    return str(codigo) if codigo else "sem código"
