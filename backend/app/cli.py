import argparse
import getpass
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Alerta, Categoria, Movimentacao, Produto, Usuario
from app.security import definir_senha, hash_senha

CODIGO_DEMO = "OL-5W30"


def _pedir_senha(senha: str | None) -> str:
    if senha:
        if len(senha) < 8:
            raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
        return senha
    confirmacao = getpass.getpass("Senha (mín. 8 caracteres): ")
    if len(confirmacao) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
    if confirmacao != getpass.getpass("Repita a senha: "):
        raise SystemExit("As senhas não conferem.")
    return confirmacao


def criar_usuario(email: str, nome: str, senha: str | None) -> None:
    email = email.strip().lower()
    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.email == email)):
            raise SystemExit(f"Já existe um usuário com o e-mail {email}.")
        db.add(Usuario(nome=nome, email=email, senha_hash=hash_senha(_pedir_senha(senha))))
        db.commit()
    print(f"Usuário {email} criado.")


def redefinir_senha(email: str, senha: str | None) -> None:
    email = email.strip().lower()
    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            raise SystemExit(f"Nenhum usuário com o e-mail {email}.")
        definir_senha(usuario, _pedir_senha(senha))
        db.commit()
    print(f"Senha de {email} redefinida.")


def _obter_ou_criar_categoria(db, nome: str) -> Categoria:
    categoria = db.scalar(select(Categoria).where(Categoria.nome == nome))
    if categoria is None:
        categoria = Categoria(nome=nome)
        db.add(categoria)
        db.flush()
    return categoria


def seed_demo() -> None:
    agora = datetime.now(timezone.utc)
    with SessionLocal() as db:
        if db.scalar(select(Produto).where(Produto.codigo == CODIGO_DEMO)):
            print("Dados de demonstração já existem. Nada foi alterado.")
            return
        usuario = db.scalar(select(Usuario).order_by(Usuario.id))
        if usuario is None:
            raise SystemExit("Crie um usuário antes com: python -m app.cli criar-usuario")

        lubrificantes = _obter_ou_criar_categoria(db, "Lubrificantes")
        filtros = _obter_ou_criar_categoria(db, "Filtros")
        freios = _obter_ou_criar_categoria(db, "Freios")
        motor = _obter_ou_criar_categoria(db, "Motor")
        eletrica = _obter_ou_criar_categoria(db, "Elétrica")

        def produto(**campos) -> Produto:
            item = Produto(**campos)
            db.add(item)
            db.flush()
            return item

        def movimento(item: Produto, tipo: str, quantidade: str, dias_atras: int,
                      motivo: str | None = None, custo: str | None = None,
                      fornecedor: str | None = None, inventario: bool = False) -> None:
            db.add(
                Movimentacao(
                    produto_id=item.id,
                    tipo=tipo,
                    quantidade=Decimal(quantidade),
                    data_hora=agora - timedelta(days=dias_atras),
                    motivo=motivo,
                    custo_unitario=Decimal(custo) if custo else None,
                    fornecedor=fornecedor,
                    usuario_id=usuario.id,
                    inventario_inicial=inventario,
                )
            )

        oleo = produto(
            nome="Óleo 5W30 sintético", codigo=CODIGO_DEMO, categoria_id=lubrificantes.id,
            unidade="L", custo_unitario=Decimal("42.90"), percentual_alerta=Decimal(20),
            localizacao="Prateleira A1",
        )
        movimento(oleo, "entrada", "100", 40, custo="38.50", fornecedor="Distribuidora Motor Sul")
        movimento(oleo, "saida", "30", 25, motivo="consumo")
        movimento(oleo, "saida", "25", 15, motivo="consumo")
        movimento(oleo, "saida", "20", 6, motivo="consumo")
        movimento(oleo, "saida", "7", 2, motivo="perda")

        filtro = produto(
            nome="Filtro de óleo", codigo="FO-001", categoria_id=filtros.id, unidade="un",
            custo_unitario=Decimal("22.00"), localizacao="Gaveta 2",
        )
        movimento(filtro, "entrada", "20", 35, custo="18.00", fornecedor="Autopeças Central")
        movimento(filtro, "saida", "4", 9, motivo="consumo")

        pastilha = produto(
            nome="Pastilha de freio dianteira", codigo="PA-DIANT", categoria_id=freios.id,
            unidade="jogo", custo_unitario=Decimal("120.00"), localizacao="Gaveta 4",
        )
        movimento(pastilha, "entrada", "5", 60, custo="120.00", fornecedor="Autopeças Central")

        correia = produto(
            nome="Correia dentada", codigo="CD-001", categoria_id=motor.id, unidade="un",
            custo_unitario=Decimal("180.00"),
        )
        movimento(correia, "entrada", "2", 90, custo="180.00", fornecedor="Distribuidora Motor Sul")

        lampada = produto(
            nome="Lâmpada H7", codigo="LA-H7", categoria_id=eletrica.id, unidade="un",
            custo_unitario=Decimal("15.00"), estoque_minimo=Decimal(4),
        )
        movimento(lampada, "entrada", "10", 20, custo="15.00", fornecedor="Elétrica Norte")
        movimento(lampada, "saida", "6", 3, motivo="consumo")

        db.flush()
        db.add_all(
            [
                Alerta(produto_id=oleo.id, saldo_no_momento=Decimal(18), limite=Decimal(20), criado_em=agora - timedelta(days=2)),
                Alerta(produto_id=lampada.id, saldo_no_momento=Decimal(4), limite=Decimal(4), criado_em=agora - timedelta(days=3)),
            ]
        )
        db.commit()
    print("Dados de demonstração criados.")


def main(argumentos: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Ferramentas de linha de comando do EstoqueCerto.")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    criar = subcomandos.add_parser("criar-usuario", help="Cria um usuário.")
    criar.add_argument("--email", required=True)
    criar.add_argument("--nome", required=True)
    criar.add_argument("--senha", help="Se omitida, será pedida de forma oculta.")

    redefinir = subcomandos.add_parser("redefinir-senha", help="Redefine a senha de um usuário.")
    redefinir.add_argument("--email", required=True)
    redefinir.add_argument("--senha", help="Se omitida, será pedida de forma oculta.")

    subcomandos.add_parser("seed-demo", help="Cria dados de exemplo da documentação (Apêndice B).")

    args = parser.parse_args(argumentos)
    try:
        if args.comando == "criar-usuario":
            criar_usuario(args.email, args.nome, args.senha)
        elif args.comando == "redefinir-senha":
            redefinir_senha(args.email, args.senha)
        elif args.comando == "seed-demo":
            seed_demo()
    except SystemExit:
        raise
    except Exception as erro:
        print(f"Falha: {erro}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
