from decimal import Decimal

CABECALHO = "nome;codigo;categoria;unidade;custo_unitario;estoque_minimo;percentual_alerta;localizacao;quantidade_inicial"


def _enviar(cliente, conteudo: str):
    return cliente.post(
        "/api/produtos/importar",
        files={"arquivo": ("produtos.csv", conteudo.encode("utf-8"), "text/csv")},
    )


def test_importacao_cria_produtos_categorias_e_inventario_inicial(cliente):
    conteudo = "\n".join(
        [
            CABECALHO,
            "Filtro de óleo;FO-100;Filtros;un;35,90;2;20;Prateleira A;10",
            "Correia dentada;CD-7;Correias;un;120,00;;;Prateleira B;4",
            ";SEMNOME;;un;;;;;",
            "Vela;VL-1;Filtros;un;abc;;;;",
            "Pastilha;FO-100;;un;;;;;",
            "Mangueira;;;un;;;150;;",
            "Fluido de freio;FL-9;Fluidos;L;18,5;;;;2,5",
        ]
    )

    resposta = _enviar(cliente, conteudo)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["criados"] == 3
    assert corpo["ignorados"] == [
        {"linha": 4, "motivo": "Nome obrigatório."},
        {"linha": 5, "motivo": "Custo unitário inválido: abc."},
        {"linha": 6, "motivo": "Código já cadastrado: FO-100."},
        {"linha": 7, "motivo": "Percentual de alerta deve estar entre 0 e 100."},
    ]

    produtos = {item["nome"]: item for item in cliente.get("/api/produtos").json()}
    assert set(produtos) == {"Correia dentada", "Filtro de óleo", "Fluido de freio"}
    filtro = produtos["Filtro de óleo"]
    assert Decimal(str(filtro["saldo"])) == Decimal("10")
    assert Decimal(str(filtro["custo_unitario"])) == Decimal("35.90")
    assert filtro["categoria_nome"] == "Filtros"
    assert Decimal(str(produtos["Fluido de freio"]["saldo"])) == Decimal("2.5")
    assert produtos["Fluido de freio"]["unidade"] == "L"

    historico = cliente.get("/api/movimentacoes", params={"produto_id": filtro["id"]}).json()["itens"]
    assert len(historico) == 1
    assert historico[0]["tipo"] == "ajuste"
    assert historico[0]["motivo"] == "Inventário inicial"

    nomes_categorias = {item["nome"] for item in cliente.get("/api/categorias").json()}
    assert nomes_categorias == {"Filtros", "Correias", "Fluidos"}


def test_importacao_aceita_separador_virgula_e_gera_alerta_quando_preciso(cliente):
    conteudo = "\n".join(
        [
            "nome,codigo,unidade,estoque_minimo,quantidade_inicial",
            "Bateria 60Ah,BT-60,un,5,1",
        ]
    )

    resposta = _enviar(cliente, conteudo)

    assert resposta.json() == {"criados": 1, "ignorados": []}
    alertas = cliente.get("/api/alertas", params={"situacao": "ativo"}).json()
    assert len(alertas) == 1
    assert alertas[0]["produto_nome"] == "Bateria 60Ah"


def test_importacao_recusa_cabecalho_sem_nome(cliente):
    resposta = _enviar(cliente, "codigo;unidade\nFO-1;un")

    assert resposta.status_code == 422
    assert resposta.json() == {
        "detail": "Cabeçalho inválido: a primeira linha precisa ter a coluna nome."
    }


def test_importacao_recusa_arquivo_vazio(cliente):
    resposta = _enviar(cliente, "   \n")

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "O arquivo está vazio."}


def test_importacao_recusa_arquivo_acima_de_2_mb(cliente):
    conteudo = CABECALHO + "\n" + ("Produto;;;un;;;;;1\n" * 200_000)

    resposta = _enviar(cliente, conteudo)

    assert resposta.status_code == 413


def test_modelo_de_importacao_traz_cabecalho_completo(cliente):
    resposta = cliente.get("/api/produtos/modelo-importacao.csv")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "text/csv; charset=utf-8"
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    assert CABECALHO in resposta.content.decode("utf-8-sig").splitlines()[0]
