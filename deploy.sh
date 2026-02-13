#!/bin/bash

# Atualiza o repositório
git pull origin main

# Ativa o ambiente virtual (ajuste o caminho se necessário)
source .venv/bin/activate

# Instala dependências
pip install -r requirements.txt

# Reinicia o serviço (ajuste conforme seu gerenciador de processos, ex: systemd, supervisor)
# systemctl restart portal-cobranca

# Comentário vazio para teste de trigger
#
