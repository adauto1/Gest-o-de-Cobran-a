# 🏦 Contexto do Projeto: Gestão de Cobrança (Portal Móveis)

Este arquivo serve como um guia completo de arquitetura, funcionalidades e estado técnico para qualquer desenvolvedor ou IA que assuma o projeto.

## 🏗️ Arquitetura e Tecnologias
- **Backend:** FastAPI (Python 3.10+)
- **Frontend:** Jinja2 Templates + HTML5 + Vanilla CSS + JavaScript (Lucide Icons para ícones)
- **Banco de Dados:** SQLite (localizado em `./data/app.db`)
- **Integração WhatsApp:** Z-API (Configuração dinâmica via banco de dados)
- **Segurança:** Autenticação baseada em sessão com controle de acesso por Roles (ADMIN e OPERADOR)

## 📁 Estrutura de Diretórios
- `app/`: Código fonte principal
  - `api/routers/`: Endpoints da aplicação (Fila, Clientes, Ações, Configurações)
  - `core/`: Configurações de banco, web (render/auth) e helpers globais
  - `services/`: Lógica de fundo (Notificações de robô e envio de WhatsApp)
  - `models.py`: Definições das tabelas SQLAlchemy
  - `schemas.py`: Validações Pydantic
  - `templates/`: Interface HTML (Dashboard, Clientes, etc.)
- `data/`: Contém o banco de dados de produção `app.db`
- `.github/workflows/`: Automação de deploy via GitHub Actions

## 🚀 Ciclo de Deploy
O deploy é automatizado via GitHub Actions sempre que um push é feito na branch `main`.
1. O workflow conecta via SSH ao servidor Hostinger (`103.199.187.246`).
2. Executa o script `/home/deploy/deploy.sh`.
3. O script atualiza o código, instala dependências e reinicia o serviço `gestor-cobranca`.

## 🛠️ Funcionalidades Críticas
1. **Robô Financeiro:** Loop que roda entre 08h e 19h. Envia resumo das promessas de pagamento do dia para usuários ativos na tabela `financial_users`.
2. **Fila de Prioridade:** Algoritmo dinâmico que ordena clientes por nível de criticidade e atraso.
3. **Registro de Contatos:** Modal para documentar ligações/mensagens, com suporte a registro de "Promessas de Pagamento" (exige valor e data).

## ⚠️ Observações de Segurança e Configurações
- **SESSION_SECRET:** Deve ser configurado via variável de ambiente ou arquivo `.env` para produção.
- **Configuração Z-API:** Instância e Token devem ser configurados no painel de Configurações do sistema para que o WhatsApp funcione.

## 📅 Histórico Recente de Melhorias (Fev/2026)
- Refatoração total do Dashboard para layout Full Width.
- Centralização da lógica de status de inadimplência em `app.core.helpers.get_status_label`.
- Otimização de performance na fila (remoção de N+1 queries).
- Correção do robô de notificações para usar credenciais dinâmicas do banco.
- Implementação de campo de valor prometido no modal de registro de contato.

## 🛡️ Regras de Desenvolvimento e Banco de Dados (🚨 MANDATÓRIO - SEM EXCEÇÕES)
Para evitar quebras no ambiente de produção (VPS), as seguintes regras devem ser seguidas rigorosamente por qualquer desenvolvedor ou IA:

1. **Alterações no Modelo:** Sempre que adicionar uma nova coluna em `app/models.py`, você **DEVE OBRIGATORIAMENTE** adicionar a linha de migração correspondente no arquivo `deploy.sh` no **mesmo commit**.
2. **Formato da Migração:** Use o comando `sqlite3` com proteção contra erro:
   ```bash
   sqlite3 "$APP_DIR/data/app.db" "ALTER TABLE nome_tabela ADD COLUMN nome_coluna TIPO;" 2>/dev/null || true
   ```
3. **Commit Atômico:** Nunca faça push de código que dependa de novas colunas sem que a migração correspondente esteja incluída no **mesmo commit**.
4. **Proteção:** O sufixo `2>/dev/null || true` é **obrigatório** para evitar que o deploy falhe caso a coluna já tenha sido criada anteriormente.

---
*Documentação atualizada em: 18/02/2026*
