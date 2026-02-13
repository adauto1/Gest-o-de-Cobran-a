# 🏦 Portal Móveis — Gestor de Cobrança

Sistema de gestão de cobrança com integração ERP, régua de cobrança automática e painel de indicadores.

## 🚀 Como fazer o Deploy (Hostinger VPS)

Este guia assume que você está usando uma VPS Ubuntu na Hostinger.

### 1. Preparação na VPS
Acesse sua VPS via SSH e instale o Docker e Docker Compose:
```bash
sudo apt update
sudo apt install docker.io docker-compose -y
sudo systemctl enable --now docker
```

### 2. Configuração do Repositório
No seu GitHub, crie um repositório e faça o push deste código:
```bash
git init
git add .
git commit -m "Initial production release"
git remote add origin https://github.com/SEU-USUARIO/SEU-REPO.git
git push -u origin main
```

### 3. Deploy via Docker Compose
Na sua VPS, clone o repositório e inicie os serviços:
```bash
git clone https://github.com/SEU-USUARIO/SEU-REPO.git
cd SEU-REPO
docker-compose up -d --build
```

### 4. Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto na VPS:
```bash
SESSION_SECRET=uma-chave-muito-segura
DATABASE_URL=sqlite:///./data/app.db
DEFAULT_ADMIN_EMAIL=admin@portalmoveis.local
DEFAULT_ADMIN_PASSWORD=SuaSenhaSeguraAqui
```

### 5. Acesso
O sistema estará disponível na porta `8000` do IP da sua VPS.
Recomendamos configurar um **Nginx Reverse Proxy** com SSL (Certbot) para produção.

---
## 🛠 Estrutura do Projeto
- `app/`: Código fonte FastAPI.
- `data/`: Diretório persistente para o banco de dados SQLite.
- `Dockerfile`: Configuração da imagem de produção (Gunicorn + Uvicorn).
- `docker-compose.yml`: Orquestração de containers.

## 📦 Dependências Principais
- FastAPI / SQLAlchemy
- Pandas (Processamento de ERP)
- Gunicorn (Servidor de Produção)
- Lucide Icons / Vanilla CSS
