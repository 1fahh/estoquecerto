import time

import pytest
from fastapi.testclient import TestClient

SENHA_TESTE = "senha-de-teste-123"

ROTAS_PROTEGIDAS = [
    ("GET", "/api/auth/me"),
    ("GET", "/api/categorias"),
    ("GET", "/api/produtos"),
    ("GET", "/api/produtos/1"),
    ("GET", "/api/movimentacoes"),
    ("GET", "/api/alertas"),
    ("GET", "/api/relatorios/painel"),
    ("GET", "/api/relatorios/parados"),
    ("GET", "/api/relatorios/exportar/estoque.csv"),
    ("GET", "/api/configuracoes"),
    ("POST", "/api/movimentacoes/entrada"),
]


def test_login_valido_devolve_token_bearer(anonimo, usuario):
    resposta = anonimo.post("/api/auth/login", json={"email": usuario.email, "senha": SENHA_TESTE})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]
    assert corpo["usuario"] == {"id": usuario.id, "nome": usuario.nome, "email": usuario.email}


@pytest.mark.parametrize(
    ("email", "senha"),
    [
        ("teste@estoquecerto.local", "senha-errada"),
        ("ninguem@estoquecerto.local", SENHA_TESTE),
    ],
)
def test_login_invalido_retorna_401_com_mensagem_em_portugues(anonimo, usuario, email, senha):
    resposta = anonimo.post("/api/auth/login", json={"email": email, "senha": senha})

    assert resposta.status_code == 401
    assert resposta.json() == {"detail": "E-mail ou senha incorretos."}


def test_login_tem_limite_de_tentativas_por_ip(anonimo, usuario):
    for _ in range(10):
        anonimo.post("/api/auth/login", json={"email": usuario.email, "senha": "errada"})

    resposta = anonimo.post("/api/auth/login", json={"email": usuario.email, "senha": SENHA_TESTE})

    assert resposta.status_code == 429


@pytest.mark.parametrize(("metodo", "caminho"), ROTAS_PROTEGIDAS)
def test_rotas_exigem_token(anonimo, metodo, caminho):
    resposta = anonimo.request(metodo, caminho, json={})

    assert resposta.status_code == 401
    assert resposta.headers["www-authenticate"] == "Bearer"


def test_token_invalido_e_recusado(anonimo):
    resposta = anonimo.get("/api/produtos", headers={"Authorization": "Bearer nao-e-um-jwt"})

    assert resposta.status_code == 401


def test_token_com_bearer_valido_e_aceito(cliente):
    assert cliente.get("/api/auth/me").status_code == 200


def test_trocar_senha_exige_senha_atual_correta(cliente, anonimo, usuario):
    recusada = cliente.post(
        "/api/auth/trocar-senha",
        json={"senha_atual": "errada", "nova_senha": "nova-senha-123"},
    )
    assert recusada.status_code == 400

    aceita = cliente.post(
        "/api/auth/trocar-senha",
        json={"senha_atual": SENHA_TESTE, "nova_senha": "nova-senha-123"},
    )
    assert aceita.status_code == 204

    assert anonimo.post("/api/auth/login", json={"email": usuario.email, "senha": "nova-senha-123"}).status_code == 200


def test_health_informa_banco_disponivel(anonimo):
    resposta = anonimo.get("/api/health")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco": "ok"}


def test_cabecalhos_de_seguranca_estao_presentes(anonimo):
    resposta = anonimo.get("/api/health")

    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in resposta.headers["Strict-Transport-Security"]


def test_desempenho_com_500_produtos_e_movimentos(cliente: TestClient, sql, usuario):
    sql(
        "INSERT INTO produtos (nome, unidade, custo_unitario, percentual_alerta, ativo) "
        "SELECT 'Produto de carga ' || g, 'un', (g % 50) + 1, 20, true FROM generate_series(1, 500) g"
    )
    sql(
        "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_hora, usuario_id, inventario_inicial) "
        "SELECT id, 'entrada', 100, now() - interval '40 days', :uid, false FROM produtos",
        {"uid": usuario.id},
    )
    sql(
        "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_hora, usuario_id, inventario_inicial, motivo) "
        "SELECT id, 'saida', 10 + (id % 80), now() - interval '2 days', :uid, false, 'consumo' FROM produtos",
        {"uid": usuario.id},
    )

    inicio = time.perf_counter()
    produtos = cliente.get("/api/produtos")
    tempo_produtos = time.perf_counter() - inicio

    inicio = time.perf_counter()
    painel = cliente.get("/api/relatorios/painel")
    tempo_painel = time.perf_counter() - inicio

    assert produtos.status_code == 200
    assert len(produtos.json()) == 500
    assert tempo_produtos < 2, f"GET /api/produtos levou {tempo_produtos:.2f} s"
    assert painel.status_code == 200
    assert painel.json()["produtos_ativos"] == 500
    assert tempo_painel < 2, f"GET /api/relatorios/painel levou {tempo_painel:.2f} s"
