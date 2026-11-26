"""Envio de e-mail pela API do Brevo e escolha do provedor (Brevo ou SMTP).

Nenhum teste usa a rede: httpx.post é trocado por um dublê que guarda a chamada,
e o smtplib é trocado por um dublê que falha se for usado.
"""

from datetime import datetime

import httpx
import pytest

from core import integracoes
from services import brevo, envio_email
from services.LoginService import email as email_login
from services.RecuperacaoService import email as email_recuperacao

CHAVE = "xkeysib-chave-de-teste"
REMETENTE = "nao-responda@simplemark.test"
DESTINO = "paciente@example.com"
VARIAVEIS = ("EMAIL_PROVEDOR", "BREVO_API_KEY", "BREVO_API_URL", "EMAIL_REMETENTE", "EMAIL_REMETENTE_NOME")


class _HttpFalso:
    """Substitui httpx.post: guarda as chamadas e devolve a resposta configurada."""

    def __init__(self, status: int = 201, corpo: dict | None = None, erro: Exception | None = None) -> None:
        self.chamadas: list[dict] = []
        self.status = status
        self.corpo = corpo if corpo is not None else {"messageId": "<id@brevo>"}
        self.erro = erro

    def __call__(self, url, *, json, headers, timeout):
        self.chamadas.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.erro is not None:
            raise self.erro
        return httpx.Response(self.status, json=self.corpo, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    """Começa cada teste sem variáveis de e-mail e com o SMTP proibido."""
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)

    def _smtp_proibido(*_args, **_kwargs):
        raise AssertionError("O SMTP não deveria ser usado com o Brevo ativo.")

    monkeypatch.setattr("smtplib.SMTP_SSL", _smtp_proibido)
    monkeypatch.setattr("smtplib.SMTP", _smtp_proibido)


@pytest.fixture
def brevo_ativo(monkeypatch):
    """Configura o Brevo e devolve o dublê do httpx.post."""
    monkeypatch.setenv("BREVO_API_KEY", CHAVE)
    monkeypatch.setenv("EMAIL_REMETENTE", REMETENTE)
    falso = _HttpFalso()
    monkeypatch.setattr(brevo.httpx, "post", falso)
    return falso


# ---------------------------------------------------------------- provedor


def test_sem_configuracao_usa_smtp():
    assert integracoes.email_provedor() == "smtp"


def test_com_chave_do_brevo_usa_brevo(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", CHAVE)
    assert integracoes.email_provedor() == "brevo"


def test_email_provedor_explicito_vence_a_chave(monkeypatch):
    monkeypatch.setenv("BREVO_API_KEY", CHAVE)
    monkeypatch.setenv("EMAIL_PROVEDOR", "SMTP")
    assert integracoes.email_provedor() == "smtp"


def test_email_provedor_desconhecido_e_recusado(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVEDOR", "sendgrid")
    with pytest.raises(ValueError):
        integracoes.email_provedor()


# ---------------------------------------------------------------- cliente do Brevo


def test_envia_para_a_api_com_chave_remetente_e_conteudo(brevo_ativo, monkeypatch):
    monkeypatch.setenv("EMAIL_REMETENTE_NOME", "Equipe SimpleMark")

    brevo.enviar_pelo_brevo(DESTINO, "Assunto", "Texto", "<p>HTML</p>")

    chamada = brevo_ativo.chamadas[0]
    assert chamada["url"] == "https://api.brevo.com/v3/smtp/email"
    assert chamada["headers"]["api-key"] == CHAVE
    assert chamada["timeout"] == brevo.TIMEOUT_BREVO_SEGUNDOS
    assert chamada["json"] == {
        "sender": {"name": "Equipe SimpleMark", "email": REMETENTE},
        "to": [{"email": DESTINO}],
        "subject": "Assunto",
        "textContent": "Texto",
        "htmlContent": "<p>HTML</p>",
    }


def test_sem_html_gera_html_escapado_a_partir_do_texto(brevo_ativo):
    brevo.enviar_pelo_brevo(DESTINO, "Assunto", "Olá <b>!\n\nLinha 1\nLinha 2")

    corpo = brevo_ativo.chamadas[0]["json"]
    assert corpo["sender"]["name"] == "SimpleMark"
    assert corpo["htmlContent"] == "<p>Olá &lt;b&gt;!</p><p>Linha 1<br>Linha 2</p>"


def test_sem_chave_ou_remetente_falha_sem_chamar_a_api(monkeypatch):
    falso = _HttpFalso()
    monkeypatch.setattr(brevo.httpx, "post", falso)
    monkeypatch.setenv("BREVO_API_KEY", CHAVE)

    with pytest.raises(brevo.ErroBrevo, match="EMAIL_REMETENTE"):
        brevo.enviar_pelo_brevo(DESTINO, "Assunto", "Texto")
    assert falso.chamadas == []


def test_recusa_da_api_vira_erro_sem_expor_a_chave(brevo_ativo):
    brevo_ativo.status = 401
    brevo_ativo.corpo = {"code": "unauthorized", "message": "Key not found"}

    with pytest.raises(brevo.ErroBrevo) as erro:
        brevo.enviar_pelo_brevo(DESTINO, "Assunto", "Texto")

    assert "401" in str(erro.value)
    assert "unauthorized" in str(erro.value)
    assert CHAVE not in str(erro.value)


def test_falha_de_conexao_vira_erro_brevo(brevo_ativo):
    brevo_ativo.erro = httpx.ConnectTimeout("tempo esgotado")

    with pytest.raises(brevo.ErroBrevo, match="ConnectTimeout"):
        brevo.enviar_pelo_brevo(DESTINO, "Assunto", "Texto")


# ---------------------------------------------------------------- quem envia


def test_codigo_de_login_sai_pelo_brevo(brevo_ativo):
    email_login.enviar_codigo_login(DESTINO, "123456")

    corpo = brevo_ativo.chamadas[0]["json"]
    assert corpo["to"] == [{"email": DESTINO}]
    assert corpo["subject"] == email_login.ASSUNTO
    assert "123456" in corpo["textContent"]
    assert "123456" in corpo["htmlContent"]


def test_codigo_de_recuperacao_sai_pelo_brevo(brevo_ativo):
    email_recuperacao.enviar_codigo_recuperacao(DESTINO, "654321", 15)

    corpo = brevo_ativo.chamadas[0]["json"]
    assert corpo["subject"] == email_recuperacao.ASSUNTO
    assert "654321" in corpo["textContent"]
    assert "15 minutos" in corpo["textContent"]


def test_falha_no_brevo_sobe_para_o_login(brevo_ativo):
    """O ServicoCodigoLogin captura a exceção e responde 503."""
    brevo_ativo.status = 500

    with pytest.raises(brevo.ErroBrevo):
        email_login.enviar_codigo_login(DESTINO, "123456")


def _dados_consulta() -> envio_email.DadosEmailConsulta:
    return envio_email.DadosEmailConsulta(
        email_paciente=DESTINO,
        nome_paciente="Ana",
        nome_profissional="Dr. Carlos",
        inicio=datetime(2026, 1, 20, 10, 0),
        meet_link="https://meet.jit.si/simplemark-sala",
    )


def test_email_da_teleconsulta_sai_pelo_brevo_com_texto_e_html(brevo_ativo):
    envio_email.enviar_email(envio_email.email_confirmacao(_dados_consulta()))

    corpo = brevo_ativo.chamadas[0]["json"]
    assert corpo["to"] == [{"email": DESTINO}]
    assert corpo["subject"] == "Sua teleconsulta está confirmada"
    assert "https://meet.jit.si/simplemark-sala" in corpo["textContent"]
    assert '<a href="https://meet.jit.si/simplemark-sala">' in corpo["htmlContent"]


def test_falha_no_brevo_vira_erro_envio_email_na_teleconsulta(brevo_ativo):
    """A videochamada só tenta de novo quando recebe ErroEnvioEmail."""
    brevo_ativo.status = 400
    brevo_ativo.corpo = {"code": "invalid_parameter"}

    with pytest.raises(envio_email.ErroEnvioEmail, match="invalid_parameter"):
        envio_email.enviar_email(envio_email.email_confirmacao(_dados_consulta()))
