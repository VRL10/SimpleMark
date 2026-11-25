"""Configuração de CORS da API."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_ORIGENS_PADRAO = [
    "https://simplemark-frontend.onrender.com",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]


def configurar_cors(app: FastAPI) -> None:
    """Configura CORS, permitindo acrescentar origens por CORS_ORIGENS."""
    origens = list(_ORIGENS_PADRAO)
    configuradas = os.getenv("CORS_ORIGENS", "")
    for origem in configuradas.split(","):
        origem = origem.strip()
        if origem and origem not in origens:
            origens.append(origem)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origens,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
