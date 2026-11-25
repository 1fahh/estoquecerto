from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


def _saldo_no_banco(sql, produto_id: int) -> Decimal:
    linha = sql(
        "SELECT COALESCE(SUM(CASE WHEN tipo = 'saida' THEN -quantidade ELSE quantidade END), 0) "
        "FROM movimentacoes WHERE produto_id = :pid",
        {"pid": produto_id},
    )
    return Decimal(linha[0][0])


def test_saldo_e_soma_das_entradas_menos_saidas_e_ajustes(cliente, criar_produto, movimentar, sql):
    produto = criar_produto(custo_unitario=10)
    movimentar("entrada", produto_id=produto["id"], quantidade=50, custo_unitario=10)
    movimentar("saida", produto_id=produto["id"], quantidade=12, motivo="consumo")
    movimentar("ajuste", produto_id=produto["id"], variacao=-3, justificativa="Quebra no transporte")

    api = cliente.get(f"/api/produtos/{produto['id']}").json()
    assert Decimal(str(api["saldo"])) == Decimal("35")
    assert Decimal(str(api["saldo"])) == _saldo_no_banco(sql, produto["id"])

    historico = cliente.get("/api/movimentacoes", params={"produto_id": produto["id"]}).json()
    assert historico["total"] == 3
    saldos_apos = [item["saldo_apos"] for item in reversed(historico["itens"])]
    assert saldos_apos == [50, 38, 35]


def test_saida_maior_que_o_saldo_e_recusada_com_mensagem_clara(cliente, criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=26)

    resposta = cliente.post(
        "/api/movimentacoes/saida",
        json={"produto_id": produto["id"], "quantidade": 30, "motivo": "consumo"},
    )

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "Saldo insuficiente: disponível 26 un, saída pedida 30 un."}
    assert cliente.get(f"/api/produtos/{produto['id']}").json()["saldo"] == 26


def test_saida_com_motivo_outro_anexa_detalhe(cliente, criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=5)

    registro = movimentar(
        "saida",
        produto_id=produto["id"],
        quantidade=1,
        motivo="outro",
        motivo_detalhe="Peça trincada",
    )

    assert registro["movimentacao"]["motivo"] == "outro: Peça trincada"


def test_alerta_do_apendice_b_nao_duplica_e_encerra_ao_repor(cliente, criar_produto, movimentar):
    produto = criar_produto(nome="Pastilha de freio")
    pid = produto["id"]

    entrada = movimentar("entrada", produto_id=pid, quantidade=100)
    assert entrada["alerta"] is None
    assert entrada["limite"] == 20

    disparo = movimentar("saida", produto_id=pid, quantidade=82, motivo="consumo")
    assert disparo["saldo_atual"] == 18
    assert disparo["limite"] == 20
    assert disparo["alerta"] == "criado"

    ativos = cliente.get("/api/alertas", params={"situacao": "ativo"}).json()
    assert len(ativos) == 1
    assert ativos[0]["produto_id"] == pid
    assert Decimal(str(ativos[0]["saldo_no_momento"])) == 18
    assert Decimal(str(ativos[0]["limite"])) == 20

    mantido = movimentar("saida", produto_id=pid, quantidade=1, motivo="consumo")
    assert mantido["alerta"] == "mantido"
    assert len(cliente.get("/api/alertas", params={"situacao": "ativo"}).json()) == 1

    reposicao = movimentar("entrada", produto_id=pid, quantidade=100)
    assert reposicao["alerta"] == "encerrado"
    assert cliente.get("/api/alertas", params={"situacao": "ativo"}).json() == []
    encerrados = cliente.get("/api/alertas", params={"situacao": "encerrado"}).json()
    assert len(encerrados) == 1
    assert encerrados[0]["encerrado_em"] is not None

    novo_disparo = movimentar("saida", produto_id=pid, quantidade=98, motivo="consumo")
    assert novo_disparo["alerta"] == "criado"
    assert len(cliente.get("/api/alertas", params={"situacao": "todos"}).json()) == 2
    assert len(cliente.get("/api/alertas", params={"situacao": "ativo"}).json()) == 1


def test_alerta_dispara_quando_saldo_fica_exatamente_no_limite(criar_produto, movimentar, cliente):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=100)

    registro = movimentar("saida", produto_id=produto["id"], quantidade=80, motivo="consumo")

    assert registro["saldo_atual"] == 20
    assert registro["alerta"] == "criado"


def test_limite_usa_o_maior_entre_estoque_minimo_e_percentual(criar_produto, movimentar):
    produto = criar_produto(estoque_minimo=30, percentual_alerta=20)
    registro = movimentar("entrada", produto_id=produto["id"], quantidade=100)
    assert registro["limite"] == 30


def test_ajuste_por_quantidade_contada_registra_variacao_com_sinal(criar_produto, movimentar, cliente):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=10)

    ajuste = movimentar(
        "ajuste",
        produto_id=produto["id"],
        quantidade_contada=7,
        justificativa="Contagem física da prateleira",
    )

    assert ajuste["movimentacao"]["tipo"] == "ajuste"
    assert ajuste["movimentacao"]["quantidade"] == -3
    assert ajuste["movimentacao"]["motivo"] == "Contagem física da prateleira"
    assert ajuste["saldo_atual"] == 7


def test_ajuste_por_variacao_positiva(criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=10)

    ajuste = movimentar("ajuste", produto_id=produto["id"], variacao=5, justificativa="Peça achada no balcão")

    assert ajuste["saldo_atual"] == 15


@pytest.mark.parametrize(
    ("corpo", "trecho"),
    [
        ({"quantidade_contada": 7}, "justificativa"),
        ({"quantidade_contada": 7, "justificativa": "ab"}, "justificativa"),
        ({"quantidade_contada": 7, "variacao": -3, "justificativa": "Contagem"}, "contada ou a variação"),
        ({"quantidade_contada": 10, "justificativa": "Contagem"}, "Nada a ajustar."),
        ({"variacao": 0, "justificativa": "Contagem"}, "Nada a ajustar."),
        ({"variacao": -50, "justificativa": "Contagem"}, "negativo"),
    ],
)
def test_ajuste_recusado_sem_justificativa_ou_sem_efeito(cliente, criar_produto, movimentar, corpo, trecho):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=10)

    resposta = cliente.post("/api/movimentacoes/ajuste", json={"produto_id": produto["id"], **corpo})

    assert resposta.status_code == 422
    assert trecho in resposta.text
    assert cliente.get(f"/api/produtos/{produto['id']}").json()["saldo"] == 10


def test_movimentacoes_nao_tem_rota_de_edicao_nem_exclusao(cliente, criar_produto, movimentar):
    produto = criar_produto()
    registro = movimentar("entrada", produto_id=produto["id"], quantidade=4)
    mov_id = registro["movimentacao"]["id"]

    for metodo, caminho in [
        ("put", f"/api/movimentacoes/{mov_id}"),
        ("patch", f"/api/movimentacoes/{mov_id}"),
        ("delete", f"/api/movimentacoes/{mov_id}"),
        ("delete", "/api/movimentacoes"),
        ("put", "/api/movimentacoes"),
    ]:
        resposta = cliente.request(metodo.upper(), caminho, json={"quantidade": 999})
        assert resposta.status_code in (404, 405), f"{metodo.upper()} {caminho} -> {resposta.status_code}"

    assert cliente.get(f"/api/produtos/{produto['id']}").json()["saldo"] == 4


@pytest.mark.parametrize(
    "comando",
    [
        "UPDATE movimentacoes SET quantidade = 999 WHERE id = {mov_id}",
        "DELETE FROM movimentacoes WHERE id = {mov_id}",
    ],
)
def test_trigger_do_banco_bloqueia_update_e_delete_direto(criar_produto, movimentar, sql, comando):
    produto = criar_produto()
    registro = movimentar("entrada", produto_id=produto["id"], quantidade=4)
    mov_id = registro["movimentacao"]["id"]

    with pytest.raises(SQLAlchemyError, match="não podem ser editadas nem excluídas"):
        sql(comando.format(mov_id=mov_id))

    restante = sql("SELECT quantidade FROM movimentacoes WHERE id = :id", {"id": mov_id})
    assert Decimal(restante[0][0]) == Decimal("4")


def test_produto_com_movimentacoes_nao_pode_ser_excluido(cliente, criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=1)

    resposta = cliente.delete(f"/api/produtos/{produto['id']}")

    assert resposta.status_code == 409
    assert resposta.json() == {"detail": "Produto com movimentações não pode ser excluído; inative-o."}


def test_produto_sem_movimentacoes_pode_ser_excluido(cliente, criar_produto):
    produto = criar_produto()

    assert cliente.delete(f"/api/produtos/{produto['id']}").status_code == 204
    assert cliente.get(f"/api/produtos/{produto['id']}").status_code == 404


def test_produto_inativo_some_da_lista_padrao_mas_segue_no_historico(
    cliente, criar_produto, movimentar
):
    produto = criar_produto(nome="Correia dentada")
    movimentar("entrada", produto_id=produto["id"], quantidade=2)

    inativado = cliente.patch(f"/api/produtos/{produto['id']}/ativo", json={"ativo": False})
    assert inativado.status_code == 200
    assert inativado.json()["ativo"] is False

    ids_padrao = [item["id"] for item in cliente.get("/api/produtos").json()]
    assert produto["id"] not in ids_padrao
    ids_todos = [item["id"] for item in cliente.get("/api/produtos", params={"ativo": "todos"}).json()]
    assert produto["id"] in ids_todos

    historico = cliente.get("/api/movimentacoes", params={"produto_id": produto["id"]}).json()
    assert historico["total"] == 1

    saida = cliente.post(
        "/api/movimentacoes/saida",
        json={"produto_id": produto["id"], "quantidade": 1, "motivo": "consumo"},
    )
    assert saida.status_code == 409


def test_movimentacao_em_produto_inexistente_retorna_404(cliente):
    resposta = cliente.post("/api/movimentacoes/entrada", json={"produto_id": 999999, "quantidade": 1})

    assert resposta.status_code == 404
    assert resposta.json() == {"detail": "Produto não encontrado."}


def test_quantidade_de_entrada_deve_ser_positiva(cliente, criar_produto):
    produto = criar_produto()

    resposta = cliente.post("/api/movimentacoes/entrada", json={"produto_id": produto["id"], "quantidade": 0})

    assert resposta.status_code == 422


def test_entrada_com_custo_atualiza_custo_do_produto(criar_produto, movimentar, cliente):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=3, custo_unitario=12.5)
    movimentar("entrada", produto_id=produto["id"], quantidade=3, custo_unitario=14)

    atual = cliente.get(f"/api/produtos/{produto['id']}").json()
    assert Decimal(str(atual["custo_unitario"])) == Decimal("14.00")
    assert Decimal(str(atual["valor_estoque"])) == Decimal("84.00")


def test_produto_sem_movimentacoes_com_alerta_ativo_pode_ser_excluido(cliente, criar_produto, sql):
    produto = criar_produto(estoque_minimo=5)
    alertas_antes = sql("SELECT COUNT(*) FROM alertas WHERE produto_id = :pid", {"pid": produto["id"]})
    assert alertas_antes[0][0] == 1

    resposta = cliente.delete(f"/api/produtos/{produto['id']}")

    assert resposta.status_code == 204
    assert sql("SELECT COUNT(*) FROM alertas WHERE produto_id = :pid", {"pid": produto["id"]})[0][0] == 0
    assert cliente.get(f"/api/produtos/{produto['id']}").status_code == 404


@pytest.mark.parametrize("quantidade", [0.0004, 0.0005, 1.2345])
def test_quantidade_com_mais_de_tres_casas_decimais_e_recusada(cliente, criar_produto, quantidade):
    produto = criar_produto()

    entrada = cliente.post("/api/movimentacoes/entrada", json={"produto_id": produto["id"], "quantidade": quantidade})
    saida = cliente.post(
        "/api/movimentacoes/saida",
        json={"produto_id": produto["id"], "quantidade": quantidade, "motivo": "consumo"},
    )

    assert entrada.status_code == 422
    assert "Use no máximo 3 casas decimais." in entrada.text
    assert saida.status_code == 422


@pytest.mark.parametrize("quantidade", [0, -2])
def test_quantidade_zero_ou_negativa_e_recusada_em_portugues(cliente, criar_produto, quantidade):
    produto = criar_produto()

    resposta = cliente.post("/api/movimentacoes/entrada", json={"produto_id": produto["id"], "quantidade": quantidade})

    assert resposta.status_code == 422
    assert "Quantidade deve ser maior que zero." in resposta.text


def test_data_hora_das_movimentacoes_segue_a_ordem_de_gravacao(cliente, criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=10)
    movimentar("saida", produto_id=produto["id"], quantidade=4, motivo="consumo")
    movimentar("entrada", produto_id=produto["id"], quantidade=1)

    itens = cliente.get("/api/movimentacoes", params={"produto_id": produto["id"]}).json()["itens"]
    cronologicos = sorted(itens, key=lambda item: item["id"])

    assert [item["data_hora"] for item in cronologicos] == sorted(item["data_hora"] for item in cronologicos)
    assert cronologicos[-1]["saldo_apos"] == itens[0]["saldo_apos"] == 7
