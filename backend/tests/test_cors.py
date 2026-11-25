from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from core.cors import configurar_cors


def _client():
    app = FastAPI()
    configurar_cors(app)

    @app.get("/ok")
    def ok():
        return {"ok": True}

    @app.get("/erro")
    def erro():
        return JSONResponse(status_code=400, content={"mensagem": "Erro de login"})

    return TestClient(app)


def test_origem_render_recebe_cabecalho_cors_em_resposta_de_erro(monkeypatch):
    origem = "https://simplemark-frontend.onrender.com"
    monkeypatch.setenv("CORS_ORIGENS", "https://outro-frontend.exemplo.com")

    response = _client().get("/erro", headers={"Origin": origem})

    assert response.status_code == 400
    assert response.headers["access-control-allow-origin"] == origem


def test_preflight_permite_origem_configurada(monkeypatch):
    origem = "https://frontend.exemplo.com"
    monkeypatch.setenv("CORS_ORIGENS", f" https://outro.exemplo.com, {origem} ")

    response = _client().options(
        "/ok",
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origem


def test_origem_nao_listada_nao_recebe_permissao_cors(monkeypatch):
    monkeypatch.setenv("CORS_ORIGENS", "https://simplemark-frontend.onrender.com")

    response = _client().get(
        "/ok",
        headers={"Origin": "https://origem-nao-autorizada.exemplo"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
