import csv
import io
import re
from decimal import Decimal


def _inserir_historico(sql, produto_id: int, quantidade: int, dias_atras: int, usuario_id: int) -> None:
    sql(
        "INSERT INTO movimentacoes (produto_id, tipo, quantidade, data_hora, usuario_id, inventario_inicial) "
        "VALUES (:pid, 'entrada', :qtd, now() - make_interval(days => :dias), :uid, false)",
        {"pid": produto_id, "qtd": quantidade, "dias": dias_atras, "uid": usuario_id},
    )


def _decimal(valor: str) -> Decimal:
    return Decimal(valor.replace(".", "").replace(",", ".") if "," in valor else valor)


def _secoes(conteudo: bytes) -> list[list[list[str]]]:
    texto = conteudo.decode("utf-8-sig")
    return [list(csv.reader(io.StringIO(trecho), delimiter=";")) for trecho in texto.split("\r\n\r\n")]


def test_produtos_parados_e_valor_imobilizado(cliente, criar_produto, movimentar, sql, usuario):
    parado = criar_produto(nome="Pastilha de freio", custo_unitario=10)
    _inserir_historico(sql, parado["id"], 5, 45, usuario.id)

    ativo = criar_produto(nome="Correia", custo_unitario=4)
    _inserir_historico(sql, ativo["id"], 5, 45, usuario.id)
    movimentar("saida", produto_id=ativo["id"], quantidade=1, motivo="consumo")

    sem_custo = criar_produto(nome="Mangueira sem preço")
    _inserir_historico(sql, sem_custo["id"], 3, 60, usuario.id)

    zerado = criar_produto(nome="Filtro zerado", custo_unitario=7)
    _inserir_historico(sql, zerado["id"], 2, 45, usuario.id)
    movimentar("saida", produto_id=zerado["id"], quantidade=2, motivo="perda")

    recente = criar_produto(nome="Recém-chegado", custo_unitario=9)
    movimentar("entrada", produto_id=recente["id"], quantidade=6)

    relatorio = cliente.get("/api/relatorios/parados").json()

    assert relatorio["dias"] == 30
    ids = [item["produto_id"] for item in relatorio["itens"]]
    assert ids == [sem_custo["id"], parado["id"]]
    por_id = {item["produto_id"]: item for item in relatorio["itens"]}
    assert por_id[parado["id"]]["dias_parado"] >= 44
    assert Decimal(str(por_id[parado["id"]]["valor"])) == Decimal("50.00")
    assert por_id[sem_custo["id"]]["valor"] is None
    assert relatorio["sem_custo_qtd"] == 1
    assert Decimal(str(relatorio["total_valor"])) == Decimal("50.00")


def test_periodo_de_parado_e_configuravel(cliente, criar_produto, sql, usuario):
    produto = criar_produto(custo_unitario=2)
    _inserir_historico(sql, produto["id"], 4, 45, usuario.id)

    assert cliente.get("/api/relatorios/parados", params={"dias": 50}).json()["itens"] == []
    assert len(cliente.get("/api/relatorios/parados", params={"dias": 40}).json()["itens"]) == 1

    cliente.put("/api/configuracoes", json={"periodo_parado_dias": 50, "percentual_alerta_padrao": 20})
    assert cliente.get("/api/relatorios/parados").json()["itens"] == []


def test_painel_reune_alertas_parados_e_registros_do_dia(cliente, criar_produto, movimentar, sql, usuario):
    parado = criar_produto(custo_unitario=10)
    _inserir_historico(sql, parado["id"], 5, 45, usuario.id)

    produto = criar_produto(nome="Óleo 5W30", custo_unitario=30)
    movimentar("entrada", produto_id=produto["id"], quantidade=10)
    movimentar("saida", produto_id=produto["id"], quantidade=9, motivo="consumo")

    painel = cliente.get("/api/relatorios/painel").json()

    assert painel["produtos_ativos"] == 2
    assert painel["total_alertas"] == 1
    assert painel["alertas_ativos"][0]["produto_id"] == produto["id"]
    assert painel["parados_qtd"] == 1
    assert Decimal(str(painel["parados_valor"])) == Decimal("50.00")
    assert painel["registros_hoje"] == 2


def test_csv_de_estoque_bate_com_a_listagem_de_produtos(cliente, criar_produto, movimentar):
    alerta = criar_produto(nome="Pastilha", custo_unitario=12.5, estoque_minimo=5)
    movimentar("entrada", produto_id=alerta["id"], quantidade=10, custo_unitario=12.5)
    movimentar("saida", produto_id=alerta["id"], quantidade=8, motivo="consumo")
    normal = criar_produto(nome="Fluido de freio", custo_unitario=20)
    movimentar("entrada", produto_id=normal["id"], quantidade=3.5, custo_unitario=20)

    resposta = cliente.get("/api/relatorios/exportar/estoque.csv")
    listagem = {item["nome"]: item for item in cliente.get("/api/produtos").json()}

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "text/csv; charset=utf-8"
    assert re.fullmatch(r'attachment; filename="estoquecerto-estoque-\d{4}-\d{2}-\d{2}\.csv"', resposta.headers["content-disposition"])
    assert resposta.content.startswith(b"\xef\xbb\xbf")

    cabecalho, *linhas = _secoes(resposta.content)[0]
    assert cabecalho[:7] == ["Produto", "Código", "Categoria", "Unidade", "Saldo", "Limite de reposição", "Situação"]
    assert len(linhas) == len(listagem) == 2
    for linha in linhas:
        produto = listagem[linha[0]]
        assert _decimal(linha[4]) == Decimal(str(produto["saldo"]))
        assert _decimal(linha[5]) == Decimal(str(produto["limite"]))
        assert linha[6] == ("Repor" if produto["em_alerta"] else "OK")
    fluido = next(linha for linha in linhas if linha[0] == "Fluido de freio")
    assert fluido[4] == "3,5"
    assert fluido[6] == "OK"
    pastilha = next(linha for linha in linhas if linha[0] == "Pastilha")
    assert pastilha[6] == "Repor"


def test_csv_de_movimentacoes_bate_com_o_historico_da_tela(cliente, criar_produto, movimentar):
    produto = criar_produto(nome="Velas de ignição")
    movimentar("entrada", produto_id=produto["id"], quantidade=10, fornecedor="Distribuidora Sul")
    movimentar("saida", produto_id=produto["id"], quantidade=3, motivo="perda")
    movimentar("ajuste", produto_id=produto["id"], variacao=-2, justificativa="Contagem física")

    resposta = cliente.get(
        "/api/relatorios/exportar/movimentacoes.csv",
        params={"produto_id": produto["id"]},
    )
    historico = cliente.get("/api/movimentacoes", params={"produto_id": produto["id"]}).json()["itens"]

    cabecalho, *linhas = _secoes(resposta.content)[0]
    assert cabecalho[0] == "Data e hora"
    assert len(linhas) == len(historico) == 3
    for linha, item in zip(linhas, historico):
        assert linha[1] == "Velas de ignição"
        assert _decimal(linha[4]) == Decimal(str(item["quantidade"]))
        assert _decimal(linha[9]) == Decimal(str(item["saldo_apos"]))
    assert linhas[0][3] == "Ajuste"
    assert linhas[0][5] == "Contagem física"


def test_csv_de_movimentacoes_filtra_por_tipo(cliente, criar_produto, movimentar):
    produto = criar_produto()
    movimentar("entrada", produto_id=produto["id"], quantidade=10)
    movimentar("saida", produto_id=produto["id"], quantidade=3, motivo="consumo")

    resposta = cliente.get("/api/relatorios/exportar/movimentacoes.csv", params={"tipo_mov": "saida"})

    _, *linhas = _secoes(resposta.content)[0]
    assert len(linhas) == 1
    assert linhas[0][3] == "Saída"


def test_csv_quinzena_traz_estoque_e_movimentacoes_em_secoes(cliente, criar_produto, movimentar):
    produto = criar_produto(nome="Juntas")
    movimentar("entrada", produto_id=produto["id"], quantidade=4)

    resposta = cliente.get("/api/relatorios/exportar/quinzena.csv")

    secoes = _secoes(resposta.content)
    assert len(secoes) == 2
    assert secoes[0][0][0] == "Produto"
    assert secoes[1][0][0] == "Data e hora"
    assert len(secoes[1]) == 2


def test_csv_de_parados_tem_linha_de_total(cliente, criar_produto, sql, usuario):
    produto = criar_produto(nome="Rolamento", custo_unitario=15)
    _inserir_historico(sql, produto["id"], 2, 40, usuario.id)

    resposta = cliente.get("/api/relatorios/exportar/parados.csv", params={"dias": 30})

    _, *linhas = _secoes(resposta.content)[0]
    assert linhas[0][0] == "Rolamento"
    assert linhas[0][4] == "30,00"
    assert linhas[-1][0] == "Total imobilizado"
    assert linhas[-1][4] == "30,00"


def test_tipo_de_exportacao_invalido_retorna_422(cliente):
    assert cliente.get("/api/relatorios/exportar/inexistente.csv").status_code == 422


def test_csv_neutraliza_formulas_e_mantem_numeros_negativos(cliente, criar_produto, movimentar):
    produto = criar_produto(nome="=HYPERLINK(\"http://x\")", codigo="+cmd", custo_unitario=10)
    movimentar("entrada", produto_id=produto["id"], quantidade=5, fornecedor="@fornecedor")
    movimentar("ajuste", produto_id=produto["id"], quantidade_contada=3, justificativa="-contagem física")

    estoque = _secoes(cliente.get("/api/relatorios/exportar/estoque.csv").content)[0][1]
    assert estoque[0] == "'=HYPERLINK(\"http://x\")"
    assert estoque[1] == "'+cmd"

    _, ajuste, entrada = _secoes(cliente.get("/api/relatorios/exportar/movimentacoes.csv").content)[0]
    assert ajuste[4] == "-2"
    assert ajuste[5] == "'-contagem física"
    assert entrada[7] == "'@fornecedor"
