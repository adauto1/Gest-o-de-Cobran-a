# Go-Live — App Cobrança Portal Móveis (Interno)

## 1) Antes de subir
- [ ] Copiar `.env.example` -> `.env`
- [ ] Trocar `SESSION_SECRET` (mínimo 32 caracteres)
- [ ] Trocar `DEFAULT_ADMIN_PASSWORD`
- [ ] Garantir que a porta 8000 está liberada no firewall (ou usar reverse proxy)

## 2) Subir na VPS (Docker)
```bash
docker compose up -d --build
```

## 3) Primeiro acesso
- URL: `http://SEU_IP:8000`
- Login admin: conforme `.env`
- Criar usuários cobradores: menu **Usuários**

## 4) Importar base
- Menu **Importar**
- Subir `clientes.csv` e `parcelas.csv` no padrão do sistema

## 5) Backup
- Rodar manual: `./scripts/backup.sh`
- Recomendo agendar no cron (diário 02:00):
```bash
crontab -e
0 2 * * * /caminho/do/projeto/scripts/backup.sh >/dev/null 2>&1
```

## 6) Atualizações
- Para atualizar versão do app: `git pull` (se estiver via git) ou substituir pasta
- Reiniciar: `docker compose up -d --build`
