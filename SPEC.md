# EstoqueCerto — Especificação técnica (contrato entre os módulos)

Fonte de verdade funcional: `docs/documentacao-v3.txt` (Documentação v3.0). Este arquivo traduz a
documentação em decisões técnicas. **Todo agente deve seguir este contrato à risca**: nomes de
tabelas, rotas, campos JSON e pastas. Se algo não estiver aqui, siga a documentação.

Design aprovado: `docs/design/F-*.dc.html` (HTML estático; leia o markup e copie o visual —
cores, raios, tamanhos, textos). Estilo "Bancada".

---

## 1. Stack (seção 10 da documentação)

| Camada | Tecnologia |
|---|---|
| Front-end | React 18 + TypeScript + Vite + react-router-dom 6. Sem biblioteca de UI. CSS próprio. |
| Back-end | Python 3.12 + FastAPI + SQLAlchemy 2 (sync) + psycopg 3 + Alembic + Pydantic 2 |
| Banco | PostgreSQL (Neon). Driver: `postgresql+psycopg://` |
| Autenticação | e-mail + senha; senha com `bcrypt`; token JWT (PyJWT, HS256, 7 dias) no header `Authorization: Bearer` |
| Notificações | E-mail via SMTP (módulo pronto, **desligado**: `EMAIL_ENABLED=false` → só registra no log) |
| Hospedagem | Render (um único web service Docker: FastAPI serve a API em `/api` e o build do React em `/`) |
| Versionamento | Git + GitHub (repo privado `1fahh/estoquecerto`) |

Por que um serviço só: mesma origem (sem CORS), HTTPS do Render cobre front e API, plano gratuito.

## 2. Estrutura de pastas

```
estoquecerto/
├── SPEC.md  README.md  Dockerfile  render.yaml  .env.example  .gitignore
├── docs/                      documentação, design, decisões
├── .github/workflows/backup.yml   backup diário (pg_dump) – RNF07
├── backend/
│   ├── requirements.txt       versões fixadas
│   ├── alembic.ini
│   ├── alembic/env.py, alembic/versions/0001_inicial.py
│   ├── app/
│   │   ├── main.py            cria FastAPI, registra routers em /api, serve static, /api/health
│   │   ├── config.py          Settings (pydantic-settings) lendo env
│   │   ├── db.py              engine, SessionLocal, get_db, Base
│   │   ├── models.py          TODOS os modelos ORM
│   │   ├── schemas.py         TODOS os schemas Pydantic de entrada/saída
│   │   ├── security.py        hash/verify senha, criar/ler JWT, dependência get_current_user
│   │   ├── services/
│   │   │   ├── estoque.py     saldo, limite, alertas, registrar movimentação (regras RN01–RN10)
│   │   │   ├── relatorios.py  parados, valor imobilizado, resumo do painel
│   │   │   ├── csv_io.py      exportar/importar CSV
│   │   │   └── notificador.py envio de e-mail (SMTP) ou log
│   │   ├── routers/
│   │   │   ├── auth.py  categorias.py  produtos.py  movimentacoes.py
│   │   │   ├── alertas.py  relatorios.py  configuracoes.py
│   │   └── cli.py             `python -m app.cli criar-usuario|redefinir-senha|seed-demo`
│   └── tests/                 pytest (critérios de aceite da seção 14)
└── frontend/
    ├── package.json  vite.config.ts  tsconfig.json  index.html
    └── src/
        ├── main.tsx  App.tsx (rotas)  styles.css (tokens)  api.ts (cliente)  auth.tsx (contexto)
        ├── types.ts           tipos espelhando os schemas da API
        ├── format.ts          formatação pt-BR (números, R$, datas)
        ├── components/        BottomNav, Icon, Sheet, Toast, ProtectedRoute, EmptyState…
        └── pages/             Login, Painel, Produtos, ProdutoForm, Saida, Entrada, Ajuste,
                               Historico, Parados, Relatorios, Alertas, ImportarCsv
```

## 3. Variáveis de ambiente (`app/config.py`)

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | obrigatória | `postgresql://…` do Neon; o código troca o prefixo para `postgresql+psycopg://` e remove `channel_binding` se der problema |
| `JWT_SECRET` | obrigatória em produção | assinatura do token |
| `JWT_EXPIRE_DAYS` | 7 | validade do token |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ADMIN_NOME` | — | se não houver nenhum usuário, o app cria este no startup (MVP = 1 usuária, premissa 5a) |
| `EMAIL_ENABLED` | `false` | liga o envio real dos alertas |
| `SMTP_HOST`, `SMTP_PORT`(587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `ALERT_EMAIL_TO` | — | SMTP com STARTTLS; `ALERT_EMAIL_TO` padrão = e-mail do usuário |
| `APP_URL` | `http://localhost:8000` | link no e-mail |
| `STATIC_DIR` | `static` | pasta do build do React servido pelo FastAPI |

## 4. Modelo de dados (seção 11) — tabelas PostgreSQL

Quantidades são `NUMERIC(12,3)` (aceita litros fracionados); dinheiro `NUMERIC(12,2)`; datas `TIMESTAMPTZ` (UTC no banco, exibidas em America/Sao_Paulo no front).

**usuarios**: `id` serial PK, `nome` varchar(120) not null, `email` varchar(254) unique not null (minúsculo), `senha_hash` varchar(255) not null, `token_versao` int not null default 0 (vai no JWT como `ver`; sobe a cada troca/redefinição de senha e derruba os tokens antigos), `criado_em` timestamptz default now().

**categorias**: `id` serial PK, `nome` varchar(80) not null, unique (case-insensitive: índice único em `lower(nome)`).

**produtos**: `id` serial PK, `nome` varchar(160) not null, `codigo` varchar(60) null (código ou referência; único quando preenchido), `categoria_id` FK categorias null, `unidade` varchar(20) not null default 'un' (valores sugeridos: un, L, jogo, kg, m, cx, par), `custo_unitario` numeric(12,2) null, `estoque_minimo` numeric(12,3) null, `percentual_alerta` numeric(5,2) not null default 20 (0–100), `localizacao` varchar(120) null, `observacoes` text null, `ativo` boolean not null default true, `criado_em` timestamptz default now(), `atualizado_em` timestamptz.
**Não existe coluna de saldo** (RN01).

**movimentacoes**: `id` bigserial PK, `produto_id` FK not null, `tipo` varchar(10) check in ('entrada','saida','ajuste') not null, `quantidade` numeric(12,3) not null, `data_hora` timestamptz not null default now(), `motivo` text null, `custo_unitario` numeric(12,2) null, `fornecedor` varchar(160) null, `usuario_id` FK usuarios not null, `inventario_inicial` boolean not null default false.
- Convenção de sinal: entrada e saída guardam `quantidade > 0`; ajuste guarda a **variação com sinal** (≠ 0).
- Saída: `motivo` obrigatório ∈ {`consumo`,`perda`,`outro`}; se `outro`, campo `motivo_detalhe` do request é anexado (`"outro: <texto>"`).
- Ajuste: `motivo` = justificativa obrigatória (mín. 3 caracteres) (RF06/RN03).
- Índices: `(produto_id, data_hora desc)`, `(tipo, data_hora desc)`.
- **Imutável** (RN03): migração cria trigger `BEFORE UPDATE OR DELETE ON movimentacoes` que lança exceção. Não existe rota de editar/apagar.

**alertas**: `id` serial PK, `produto_id` FK not null, `saldo_no_momento` numeric(12,3), `limite` numeric(12,3), `criado_em` timestamptz default now(), `encerrado_em` timestamptz null, `situacao` varchar(10) check in ('ativo','encerrado') default 'ativo', `email_enviado` boolean default false.
- Índice único parcial: `unique (produto_id) where situacao = 'ativo'` (RN06 – um alerta ativo por produto).

**configuracoes** (linha única id=1): `periodo_parado_dias` int default 30 (RN07), `percentual_alerta_padrao` numeric(5,2) default 20 (RN05).

## 5. Regras de negócio → implementação (`services/estoque.py`)

- **saldo(produto)** = Σ entrada − Σ saída + Σ ajuste (RN01). Função SQL única via `CASE`; para listas, uma query agregada com `GROUP BY` (nada de N+1, RNF02).
- **quantidade de referência** = quantidade da última `entrada` do produto; se não houver entrada, a do ajuste `inventario_inicial` positivo mais recente; senão 0.
- **limite(produto)** = `max(estoque_minimo or 0, percentual_alerta/100 × referência)` (RN04/RN05). Exemplo do Apêndice B: referência 100, 20% → limite 20; saldo 18 → alerta.
- **em_alerta** = `limite > 0 and saldo <= limite`.
- **registrar_movimentacao(db, usuario, tipo, dados)** — numa única transação (RN10):
  1. `SELECT … FROM produtos WHERE id = :id FOR UPDATE` (serializa movimentos do mesmo produto); 404 se não existe; 409 se `ativo = false` (RN09: inativo não aparece no registro).
  2. calcula saldo atual; se saída e `quantidade > saldo` → **422** com `{"detail": "Saldo insuficiente: disponível 26 un, saída pedida 30 un."}` (RN02); se ajuste deixaria saldo < 0 → 422.
  3. insere a movimentação; em entrada com `custo_unitario` informado, atualiza `produtos.custo_unitario` (último custo vale para o valor imobilizado).
  4. `avaliar_alerta(db, produto)`: recalcula saldo e limite; se em alerta e não há alerta ativo → cria alerta (e agenda e-mail); se **não** em alerta e há alerta ativo → encerra (`situacao='encerrado'`, `encerrado_em=now()`) (RN06).
  5. commit; e-mail enviado **depois** do commit (falha de e-mail nunca desfaz o registro; marca `email_enviado`).
  6. retorna `{movimentacao, saldo_anterior, saldo_atual, limite, alerta: "criado"|"encerrado"|"mantido"|null}` — a tela mostra o novo saldo como confirmação (fluxo 9.1 f).
- Ajuste aceita **`quantidade_contada`** (saldo físico; o servidor calcula a variação) **ou** `variacao`. Variação 0 → 422 "Nada a ajustar".
- Ao **editar** produto (mínimo/percentual) também roda `avaliar_alerta`.
- **Produtos parados** (RN07): `ativo` e `saldo > 0` e nenhuma `saida` nos últimos `dias` (padrão = configuração, 30). `dias_parado` = dias desde a última saída, ou desde a primeira movimentação se nunca saiu.
- **Valor imobilizado** (RN08) = `saldo × custo_unitario`, só quando há custo; produtos sem custo vêm com `valor = null` e não somam no total.
- **Inativação** (RN09): `DELETE /api/produtos/{id}` só apaga se o produto não tem movimentações; senão 409 `"Produto com movimentações não pode ser excluído; inative-o."`. Inativar = `PATCH` com `ativo=false`. Inativos somem das listas de registro (`?ativo=true` por padrão) mas seguem no histórico.

## 6. API REST (prefixo `/api`, JSON, datas ISO 8601, números decimais como **number** no JSON)

Todas exigem Bearer, exceto `POST /api/auth/login` e `GET /api/health`. Erros: `{"detail": "mensagem em português"}`.

### Auth (RF01)
- `POST /api/auth/login` `{email, senha}` → `{access_token, token_type:"bearer", usuario:{id,nome,email}}`; 401 "E-mail ou senha incorretos." Limite anti-força-bruta (em memória): 10 falhas/5 min por IP **e** por e-mail; login certo não conta. IP = último item do `X-Forwarded-For` (o que o proxy do Render acrescenta; o cliente só forja os anteriores).
- `GET /api/auth/me` → `{id,nome,email}`
- `POST /api/auth/trocar-senha` `{senha_atual, nova_senha}` (mín. 8) → TokenOut com token novo (as outras sessões caem)

### Categorias (RF03)
- `GET /api/categorias` → `[{id, nome, total_produtos}]` ordenado por nome
- `POST /api/categorias` `{nome}` → 201; 409 se nome repetido
- `PUT /api/categorias/{id}` `{nome}`

### Produtos (RF02, RF07, RF08)
Objeto **ProdutoOut**: `{id, nome, codigo, categoria_id, categoria_nome, unidade, custo_unitario, estoque_minimo, percentual_alerta, localizacao, observacoes, ativo, saldo, limite, em_alerta, quantidade_referencia, ultima_movimentacao_em, valor_estoque}`
- `GET /api/produtos?busca=&categoria_id=&situacao=todos|repor|parados&ativo=true|false|todos` → `[ProdutoOut]` (busca em nome e código, sem acento/caixa via `unaccent`-free: usar `ilike` + normalização Python)
- `GET /api/produtos/{id}` → ProdutoOut
- `POST /api/produtos` ProdutoIn `{nome, codigo?, categoria_id?, unidade, custo_unitario?, estoque_minimo?, percentual_alerta?, localizacao?, observacoes?, quantidade_inicial?}` → 201 ProdutoOut. Se `quantidade_inicial > 0`, cria ajuste `inventario_inicial=true`, motivo "Inventário inicial" (seção 13 d).
- `PUT /api/produtos/{id}` ProdutoIn (sem quantidade_inicial) → ProdutoOut (reavalia alerta)
- `PATCH /api/produtos/{id}/ativo` `{ativo: bool}` → ProdutoOut
- `DELETE /api/produtos/{id}` → 204 ou 409 (RN09)

### Movimentações (RF04, RF05, RF06, RF10)
- `POST /api/movimentacoes/entrada` `{produto_id, quantidade>0, custo_unitario?, fornecedor?}` → RegistroOut
- `POST /api/movimentacoes/saida` `{produto_id, quantidade>0, motivo: consumo|perda|outro, motivo_detalhe?}` → RegistroOut
- `POST /api/movimentacoes/ajuste` `{produto_id, quantidade_contada? | variacao?, justificativa}` → RegistroOut
- `GET /api/movimentacoes?produto_id=&tipo=entrada|saida|ajuste&de=YYYY-MM-DD&ate=YYYY-MM-DD&limite=100&offset=0` → `{itens:[MovOut], total}`; MovOut = `{id, produto_id, produto_nome, unidade, tipo, quantidade, data_hora, motivo, custo_unitario, fornecedor, usuario_nome, saldo_apos}` (`saldo_apos` = saldo acumulado após o movimento, via window function `SUM() OVER (PARTITION BY produto_id ORDER BY data_hora, id)`), ordenado do mais recente.
- `GET /api/movimentacoes/ultima-entrada/{produto_id}` → `{quantidade, custo_unitario, fornecedor, data_hora}` ou 404 (tela de entrada "usar a mesma")
- `GET /api/movimentacoes/mais-usados?limite=6` → produtos com mais saídas nos últimos 30 dias (atalhos)
- **Sem PUT/PATCH/DELETE** (RN03).

### Alertas (RF09)
- `GET /api/alertas?situacao=ativo|encerrado|todos` → `[{id, produto_id, produto_nome, unidade, saldo_no_momento, saldo_atual, limite, criado_em, encerrado_em, situacao}]`

### Relatórios (RF11, RF12, painel)
- `GET /api/relatorios/painel` → `{data, produtos_ativos, alertas_ativos:[…até 5], total_alertas, parados_qtd, parados_valor, registros_hoje}`
- `GET /api/relatorios/parados?dias=30` → `{dias, itens:[{produto_id, nome, unidade, saldo, custo_unitario, valor, dias_parado, ultima_saida_em}], total_valor, sem_custo_qtd}` ordenado por `dias_parado` desc
- `GET /api/relatorios/exportar/{tipo}.csv` com `tipo ∈ estoque|movimentacoes|parados|reposicao|quinzena` e filtros iguais às listas (`de`, `ate`, `produto_id`, `tipo_mov`, `dias`) → `text/csv; charset=utf-8`, **BOM UTF-8, separador `;`, decimal com vírgula** (abre certo no Excel pt-BR); textos que começam com `= + - @` ou tab recebem `'` na frente (proteção contra fórmula em planilha), `Content-Disposition: attachment; filename="estoquecerto-<tipo>-AAAA-MM-DD.csv"`. `quinzena` = estoque atual + movimentações dos últimos 15 dias num único CSV (duas seções separadas por linha em branco). O conteúdo bate com o que a tela mostra (critério 14 h).
- `POST /api/produtos/importar` (RF13, multipart `arquivo`) colunas: `nome;codigo;categoria;unidade;custo_unitario;estoque_minimo;percentual_alerta;localizacao;quantidade_inicial` (cabeçalho obrigatório, `;` ou `,`, decimal vírgula ou ponto). Cria categorias que não existem. Responde `{criados, ignorados:[{linha, motivo}]}`. Tudo numa transação; erro de linha → linha ignorada com motivo, não derruba o resto. Também `GET /api/produtos/modelo-importacao.csv`.

### Configurações
- `GET /api/configuracoes` / `PUT /api/configuracoes` `{periodo_parado_dias (1–365), percentual_alerta_padrao (0–100)}`

### Saúde
- `GET /api/health` → `{status:"ok", banco:"ok"}` (faz `SELECT 1`).

## 7. Notificações (`services/notificador.py`, seção 9.3)

`enviar_alerta(alerta, produto, saldo, limite)`: assunto `"[EstoqueCerto] Repor: <produto>"`, corpo com nome do produto, saldo atual, limite e link `APP_URL/produtos/<id>`. Se `EMAIL_ENABLED=false` → `logger.info("E-mail desativado; alerta …")` e retorna False. Nunca lança exceção para fora.

## 8. Front-end — telas e rotas (seção 12 + design escolhido)

| Rota | Tela | Design de referência |
|---|---|---|
| `/login` | Login (seção a) | `F-Login.dc.html` |
| `/` | Painel: saudação, botões grandes Saída/Entrada, alertas ativos com barra, 3 números (produtos, parados, hoje) | `F-Painel.dc.html` |
| `/produtos` | Lista com busca, abas Todos/Repor/Parados, `−` abre saída e `+` abre entrada já com o produto | `F-Produtos.dc.html` |
| `/produtos/novo`, `/produtos/:id` | Cadastro/edição em 3 seções numeradas, chips de categoria (+ Nova), % 10/20/30/Outro, frase de prévia do limite, Inativar, link Conferir saldo | `F-Produto.dc.html` |
| `/saida?produto=` | Painel de baixo (sheet): escolher produto (busca se não veio), chips 1–5 + Outra, motivo Consumo/Perda/Outro, botão "Tirar N <un>", aviso se vai gerar alerta. **≤ 3 interações a partir do painel** (RNF01) | `F-Saida.dc.html` |
| `/entrada?produto=` | Antes → Depois, quantidade, custo unitário (total calculado), fornecedor opcional com chips dos usados antes, aviso de alerta encerrado | `F-Entrada.dc.html` (alternativa visual em `F-Entrada-alt.dc.html`, não usar) |
| `/ajuste?produto=` | No sistema × Eu contei (± ), diferença, motivo obrigatório em opções + detalhe | `F-Ajuste.dc.html` |
| `/historico` | Filtros (produto, tipo, período); com produto escolhido mostra gráfico de barras do saldo + tabela com saldo após cada registro | `F-Historico.dc.html` |
| `/parados` | Total imobilizado, período 30/60/90, lista com saldo × custo e dias, baixar CSV | `F-Parados.dc.html` |
| `/relatorios` | Período + 4 relatórios com botão baixar (estoque, movimentações, parados, reposição) + link Importar CSV | `F-Exportar.dc.html` |
| `/alertas` | Lista de alertas ativos (e encerrados recentes) | estilo das listas |
| `/importar` | Upload CSV + link do modelo + resultado (criados/ignorados) | estilo dos formulários |
| `/conta` | Nome, trocar senha, sair, período de produto parado e % padrão | estilo dos formulários |

Regras de UI: mobile-first, largura máx. de conteúdo 480 px centralizada no desktop (RNF03), **sem rolagem horizontal** (critério 14 j), alvos de toque ≥ 44 px, `BottomNav` de 4 abas (Início, Produtos, Histórico, Relatórios) nas telas principais, textos em português do Brasil, números com `Intl.NumberFormat('pt-BR')`, R$ com `style:'currency'`. Erros da API aparecem em português no formulário (ex.: saldo insuficiente). Token salvo em `localStorage`; 401 → volta ao login.

Tokens de design (`styles.css`): `--bg:#F4F5F7; --surface:#FFFFFF; --border:#E3E6EB; --line:#F1F2F5; --text:#16181D; --text-2:#3A404C; --muted:#5B6270; --primary:#2347D6; --primary-strong:#1A36A8; --primary-soft:#E8EDFD; --primary-on:#DCE3FB; --alert:#C2410C; --alert-bar:#EA580C; --alert-soft:#FFF1E8; --alert-border:#FBD5BE; --alert-ink:#7C2D12; --alert-ink-2:#9A3412; --ok:#15803D; --ok-soft:#EAF7EE; --ok-ink:#14532D; --radius-card:20px; --radius-ctl:14px; --radius-btn:16px;` fonte `Plus Jakarta Sans` (Google Fonts, pesos 400–800).

Dev: `vite.config.ts` faz proxy de `/api` para `http://localhost:8000`. Build sai em `frontend/dist`; o Dockerfile copia para `backend/static`.

## 9. Testes (seção 14) — `backend/tests/`

pytest contra o Postgres de `TEST_DATABASE_URL` (ou `DATABASE_URL`), criando um **schema temporário** por sessão de testes (`CREATE SCHEMA test_<random>`; `search_path`), rodando as migrações Alembic nele e apagando no fim. Cobrem os critérios a–j: saldo = entradas − saídas ± ajustes; saída maior que saldo recusada com mensagem clara; alerta criado no limite e não duplicado; alerta encerrado ao subir acima do limite; movimentações não editáveis nem apagáveis (rota inexistente **e** trigger no banco); parados e valor imobilizado; CSV bate com a listagem; tempo das consultas com 500 produtos < 2 s; exemplo do Apêndice B. Comando: `cd backend && pytest -q`.

## 10. Deploy

- `Dockerfile` multi-stage: `node:22-alpine` builda o front → `python:3.12-slim` instala `requirements.txt`, copia `backend/` e o `dist` para `/app/static`, `CMD` roda `alembic upgrade head` e depois `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers` (o IP do cliente é lido em `auth.ip_do_cliente`).
- `render.yaml` (blueprint de referência): serviço web docker, plano free, `healthCheckPath: /api/health`, envs listadas na seção 3 (`sync: false` para segredos).
- Backup diário (RNF07): `.github/workflows/backup.yml` às 06:00 UTC, `pg_dump` (cliente postgres 17) do segredo `DATABASE_URL` → artifact com retenção de 30 dias; também `workflow_dispatch`. Restauração documentada no README (`pg_restore`) + PITR do Neon.
- Segurança (RNF04/18): HTTPS do Render; cabeçalhos `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Strict-Transport-Security` via middleware; nenhum dado pessoal além de nome e e-mail da usuária (RNF05/LGPD).
