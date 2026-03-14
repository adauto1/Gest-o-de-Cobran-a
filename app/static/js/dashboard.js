// dashboard.js — Lógica da fila de prioridade e modais do dashboard

// === Funil de Cobrança ===
function initFunil() {
  const steps = document.querySelectorAll('.funil-step');
  if (!steps.length) return;

  // Hover interativo por cor
  steps.forEach(step => {
    const c = step.dataset.color;
    if (!c) return;
    step.style.background    = c + '0e';
    step.style.border        = '1.5px solid ' + c + '28';
    if (step.classList.contains('no-link')) return;
    step.addEventListener('mouseenter', () => {
      step.style.transform   = 'translateY(-4px)';
      step.style.boxShadow   = '0 12px 28px ' + c + '22';
      step.style.background  = c + '1c';
      step.style.borderColor = c + '50';
    });
    step.addEventListener('mouseleave', () => {
      step.style.transform   = '';
      step.style.boxShadow   = '';
      step.style.background  = c + '0e';
      step.style.borderColor = c + '28';
    });
  });

  // Count-up animado
  document.querySelectorAll('.funil-num[data-count]').forEach(el => {
    const target = parseInt(el.dataset.count) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    const dur = 900, start = performance.now();
    (function tick(now) {
      const p = Math.min((now - start) / dur, 1);
      const e = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(e * target);
      if (p < 1) requestAnimationFrame(tick);
    })(start);
  });

  // Barra de progresso animada
  document.querySelectorAll('.funil-progress').forEach(bar => {
    let pct;
    if (bar.dataset.pct !== undefined) {
      pct = Math.min(parseFloat(bar.dataset.pct) || 0, 100);
    } else if (bar.dataset.base !== undefined) {
      const base = parseFloat(bar.dataset.base) || 1;
      pct = Math.min((parseFloat(bar.dataset.val) || 0) / base * 100, 100);
    } else return;
    requestAnimationFrame(() => setTimeout(() => { bar.style.width = pct + '%'; }, 80));
  });
}


let filaCurrentPage = 1;
let filaTotalPages = 1;
window.filaFiltroRegua = '';

// === Telefone ===
function togglePhonePopover(btn) {
  const id = btn.dataset.id;
  const pop = document.getElementById('phone-pop-' + id);
  document.querySelectorAll('.phone-popover.open, .pausa-popover.open').forEach(p => {
    if (p !== pop) p.classList.remove('open');
  });
  pop.classList.toggle('open');
  if (pop.classList.contains('open')) {
    const input = document.getElementById('phone-input-' + id);
    if (input) setTimeout(() => input.focus(), 50);
  }
}

async function salvarTelefone(clienteId) {
  const input = document.getElementById('phone-input-' + clienteId);
  const numero = input.value.trim();
  if (!numero) { alert('Digite um número.'); return; }
  try {
    const res = await fetch(`/api/customers/${clienteId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ whatsapp: numero }),
      credentials: 'same-origin'
    });
    const json = await res.json();
    if (json.success) {
      document.getElementById('phone-pop-' + clienteId).classList.remove('open');
      await loadPriorityQueue();
    } else alert('Erro: ' + json.message);
  } catch { alert('Erro de conexão.'); }
}

// === Pausa de cobrança ===
function togglePausaPopover(btn) {
  const id = btn.dataset.id;
  const pop = document.getElementById('pausa-pop-' + id);
  document.querySelectorAll('.pausa-popover.open').forEach(p => {
    if (p !== pop) p.classList.remove('open');
  });
  pop.classList.toggle('open');
}

async function confirmarPausa(clienteId) {
  const dateInput = document.getElementById('pausa-date-' + clienteId);
  const data = dateInput.value;
  if (!data) { alert('Selecione uma data.'); return; }
  try {
    const res = await fetch(`/api/customers/${clienteId}/pausar`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pausado_ate: data }),
      credentials: 'same-origin'
    });
    const json = await res.json();
    if (json.success) {
      document.getElementById('pausa-pop-' + clienteId).classList.remove('open');
      await loadPriorityQueue();
    } else alert('Erro: ' + json.message);
  } catch { alert('Erro de conexão.'); }
}

async function removerPausa(clienteId) {
  try {
    const res = await fetch(`/api/customers/${clienteId}/pausar`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pausado_ate: null }),
      credentials: 'same-origin'
    });
    const json = await res.json();
    if (json.success) {
      document.getElementById('pausa-pop-' + clienteId).classList.remove('open');
      await loadPriorityQueue();
    } else alert('Erro: ' + json.message);
  } catch { alert('Erro de conexão.'); }
}

// Fecha popovers ao clicar fora
document.addEventListener('click', function(e) {
  if (!e.target.closest('.pausa-wrap') && !e.target.closest('.phone-wrap')) {
    document.querySelectorAll('.pausa-popover.open, .phone-popover.open').forEach(p => p.classList.remove('open'));
  }
});

function filtrarFila(nivel) {
  window.filaFiltroRegua = nivel === 'TODAS' ? '' : nivel;
  ['TODAS','LEVE','MODERADA','INTENSA'].forEach(n => {
    const btn = document.getElementById('filtro-' + n);
    if (!btn) return;
    if (n === nivel) {
      btn.style.fontWeight = '600';
      if (n === 'TODAS') { btn.style.background = 'rgba(99,102,241,0.12)'; btn.style.color = '#4f46e5'; btn.style.borderColor = '#4f46e5'; }
      else if (n === 'LEVE') { btn.style.background = 'rgba(22,163,74,0.12)'; btn.style.color = '#15803d'; btn.style.borderColor = '#15803d'; }
      else if (n === 'MODERADA') { btn.style.background = 'rgba(234,179,8,0.12)'; btn.style.color = '#a16207'; btn.style.borderColor = '#ca8a04'; }
      else { btn.style.background = 'rgba(220,38,38,0.12)'; btn.style.color = '#b91c1c'; btn.style.borderColor = '#dc2626'; }
    } else {
      btn.style.background = ''; btn.style.color = 'var(--text-3)'; btn.style.borderColor = ''; btn.style.fontWeight = '';
    }
  });
  loadPriorityQueue(1);
}

async function loadPriorityQueue(page = 1) {
  if (typeof page !== 'number') page = 1;

  console.log(`[Dashboard] Carregando fila página: ${page}`);
  filaCurrentPage = page;
  const body = document.getElementById('queue-body');
  const paginDiv = document.getElementById('fila-pagination');

  try {
    const _regua = window.filaFiltroRegua || '';
    const reguaParam = _regua ? `&regua=${_regua}` : '';
    const _url = `/api/fila/prioridade?page=${page}&limit=30${reguaParam}`;
    const resp = await fetch(_url);
    if (!resp.ok) {
      const errTxt = await resp.text();
      throw new Error(`Servidor retornou erro ${resp.status}: ${errTxt}`);
    }

    const data = await resp.json();
    console.log('[Dashboard] Dados recebidos:', data);

    const isArray = Array.isArray(data);
    const items = isArray ? data : (data.items || []);
    filaTotalPages = isArray ? 1 : (data.total_pages || 1);

    // Barra de stats da carteira
    if (!isArray && data.stats) {
      const s = data.stats;
      let statsBar = document.getElementById('fila-stats-bar');
      if (!statsBar) {
        statsBar = document.createElement('div');
        statsBar.id = 'fila-stats-bar';
        statsBar.style.cssText = 'display:flex;gap:16px;flex-wrap:wrap;padding:8px 12px;background:var(--bg-2,#f8fafc);border-radius:8px;margin-bottom:12px;font-size:13px;color:var(--text-2,#555);border:1px solid var(--border,#e2e8f0);';
        const tableWrapper = body.closest('table') || body.parentElement;
        tableWrapper.parentElement.insertBefore(statsBar, tableWrapper);
      }
      const semContato = s.sem_contato_hoje || 0;
      const promessas = s.promessas_abertas || 0;
      const _filtroLabel = window.filaFiltroRegua ? ` — Régua: <strong>${window.filaFiltroRegua}</strong>` : '';
      statsBar.innerHTML = `
        <span>📋 <strong>${s.total_carteira}</strong> clientes na fila${_filtroLabel}</span>
        <span style="color:${semContato > 0 ? '#dc2626' : '#16a34a'}">📵 <strong>${semContato}</strong> sem contato hoje</span>
        <span style="color:#2563eb">🤝 <strong>${promessas}</strong> promessas abertas</span>`;
    }

    if (items.length === 0) {
      body.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text-3);">Sem clientes em atraso.</td></tr>';
      paginDiv.style.display = 'none';
      return;
    }

    const showPaging = !isArray && data.total_pages > 1;
    paginDiv.style.display = showPaging ? 'flex' : 'none';

    if (showPaging) {
      document.getElementById('fila-page-info').textContent = `Página ${data.current_page} de ${data.total_pages} (${data.total_items} clientes)`;
      document.getElementById('btn-fila-prev').disabled = data.current_page <= 1;
      document.getElementById('btn-fila-next').disabled = data.current_page >= data.total_pages;
    }

    body.innerHTML = '';
    items.forEach(item => {
      try {
        const badgeClass = item.max_atraso >= 90 ? 'critical' : (item.max_atraso >= 30 ? 'moderate' : 'warning');

        const escNome = (item.nome_cliente || 'Cliente Sem Nome')
          .replace(/\\/g, '\\\\')
          .replace(/'/g, "\\'")
          .replace(/"/g, '&quot;')
          .replace(/`/g, '\\`');

        const phoneNum = item.phone || '';
        const whatsappHtml = `
          <div class="phone-wrap">
            <button
              class="q-action-btn${phoneNum ? ' whatsapp' : ''}"
              onclick="togglePhonePopover(this)"
              title="${phoneNum ? phoneNum : 'Sem telefone — clique para adicionar'}"
              data-id="${item.cliente_id}"
              data-phone="${phoneNum}">
              <i data-lucide="${phoneNum ? 'message-circle' : 'message-circle-off'}"></i>
            </button>
            <div class="phone-popover" id="phone-pop-${item.cliente_id}">
              ${phoneNum
                ? `<div class="phone-popover-num">📱 ${phoneNum}</div>
                   <input type="tel" class="phone-popover-input" id="phone-input-${item.cliente_id}" value="${phoneNum}" placeholder="Novo número...">
                   <div class="phone-popover-btns">
                     <button class="phone-btn-ok" onclick="salvarTelefone(${item.cliente_id})">Salvar</button>
                   </div>`
                : `<div class="phone-popover-title">📵 Sem telefone cadastrado</div>
                   <input type="tel" class="phone-popover-input" id="phone-input-${item.cliente_id}" placeholder="Ex: 67999990000">
                   <div class="phone-popover-btns">
                     <button class="phone-btn-ok" onclick="salvarTelefone(${item.cliente_id})">Adicionar</button>
                   </div>`
              }
            </div>
          </div>`;

        const perfilIcons = { BOM_PAGADOR: '💚', RECORRENTE: '🔄', DIFICIL: '🔴' };
        const perfilIcon = perfilIcons[item.perfil_devedor] ? ` ${perfilIcons[item.perfil_devedor]}` : '';

        let outcomeTag = '';
        if (item.ultimo_outcome === 'PROMESSA_NAO_CUMPRIDA') {
          outcomeTag = ' <span style="color:#dc2626;font-weight:600;">⚠️ Promessa não cumprida</span>';
        } else if (item.ultimo_outcome === 'PROMESSA' || item.ultimo_outcome === 'PROMESSA_PAGAMENTO') {
          outcomeTag = ' · <span style="color:#2563eb;">🤝 Promessa</span>';
        } else if (item.ultimo_outcome) {
          const outcomeFmt = item.ultimo_outcome.replace(/_/g, ' ').toLowerCase();
          outcomeTag = ` · ${outcomeFmt}`;
        }

        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', function(e) {
          if (e.target.closest('button') || e.target.closest('a')) return;
          window.location.href = `/customers/${item.cliente_id}#parcelas`;
        });
        tr.innerHTML = `
            <td data-label="Cliente">
              <a class="q-client-name" href="/customers/${item.cliente_id}#parcelas" style="text-decoration:none; color:inherit;">${item.nome_cliente}${perfilIcon}</a>
              <div class="q-client-meta">${item.qtd_parcelas || 1} parcelas · ${item.ultimo_contato_str || 'Sem contato'}${outcomeTag}</div>
            </td>
            <td data-label="Régua" style="text-align: center;">
              <div class="regua-dot dot-${item.regua_nivel || 'LEVE'}" title="Régua: ${item.regua_nivel || 'LEVE'}"></div>
            </td>
            <td data-label="Em Aberto"><span class="q-amount">R$ ${Number(item.valor_em_aberto || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></td>
            <td data-label="Status">
              <span class="q-badge ${badgeClass}">${item.status_label || ''}</span>
            </td>
            <td data-label="Ações" onclick="event.stopPropagation()" style="cursor:default;">
              <div class="q-actions">
                <button class="q-action-btn whatsapp-manual" onclick="enviarWhatsappManual(${item.cliente_id}, '${escNome}')" title="Disparar Cobrança (Z-API)" style="background:rgba(37,211,102,0.1);color:#25d366;border-color:rgba(37,211,102,0.2);">
                  <i data-lucide="send"></i>
                </button>

                ${whatsappHtml}

                <div class="pausa-wrap">
                  <button
                    class="q-action-btn pausar${item.pausado_ate ? ' ativo' : ''}"
                    onclick="togglePausaPopover(this)"
                    title="${item.pausado_ate ? 'Pausado até ' + item.pausado_ate.split('-').reverse().join('/') : 'Pausar cobrança automática'}"
                    data-id="${item.cliente_id}"
                    data-pausado="${item.pausado_ate || ''}">
                    <i data-lucide="pause-circle"></i>
                  </button>
                  <div class="pausa-popover" id="pausa-pop-${item.cliente_id}">
                    <div class="pausa-popover-title">🟠 Pausar cobrança até:</div>
                    <input type="date" id="pausa-date-${item.cliente_id}" min="${new Date().toISOString().split('T')[0]}" value="${item.pausado_ate || ''}">
                    <div class="pausa-popover-btns">
                      <button class="pausa-btn-ok" onclick="confirmarPausa(${item.cliente_id})">Confirmar</button>
                      ${item.pausado_ate ? `<button class="pausa-btn-rm" onclick="removerPausa(${item.cliente_id})">Remover</button>` : ''}
                    </div>
                  </div>
                </div>

              </div>
            </td>`;
        body.appendChild(tr);
      } catch (errLoop) {
        console.error("Erro ao renderizar item:", item, errLoop);
      }
    });

    if (typeof lucide !== 'undefined') lucide.createIcons();
  } catch (e) {
    console.error(e);
    body.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text-3);">
      Erro ao carregar fila.<br><small style="opacity:0.6">${e.message}</small>
    </td></tr>`;
  }
}

async function enviarWhatsappManual(clienteId, nome) {
  console.log(`[WhatsApp] Iniciando envio manual para ID: ${clienteId}, Nome: ${nome}`);
  if (!confirm(`Confirma o envio de mensagem de cobrança para ${nome}?`)) return;

  try {
    const res = await fetch(`/api/whatsapp/enviar-manual/${clienteId}`, {
      method: 'POST',
      headers: { 'Accept': 'application/json' }
    });

    console.log(`[WhatsApp] Status da resposta: ${res.status}`);

    if (res.status === 401) {
      alert('Sessão expirada. Por favor, faça login novamente.');
      window.location.href = '/login';
      return;
    }

    const data = await res.json();
    console.log('[WhatsApp] Dados recebidos:', data);

    if (data.success) {
      alert(`Mensagem enviada com sucesso! (${data.modo})`);
    } else {
      alert(`Erro ao enviar: ${data.erro || 'Erro desconhecido'}`);
    }
  } catch (e) {
    console.error('[WhatsApp] Erro na requisição:', e);
    alert('Erro de conexão ao enviar mensagem. Verifique se o servidor está rodando.');
  }
}

function changeFilaPage(delta) {
  const next = filaCurrentPage + delta;
  if (next >= 1 && next <= filaTotalPages) {
    loadPriorityQueue(next);
  }
}

window.changeFilaPage = changeFilaPage;
window.enviarWhatsappManual = enviarWhatsappManual;
window.filtrarFila = filtrarFila;

// === Modal de Edição ===
function openEditModal(customerId, customerName) {
  fetch(`/api/customers/${customerId}`, { credentials: 'same-origin' })
    .then(r => r.json())
    .then(data => {
      document.getElementById('edit_customer_id').value = customerId;
      document.getElementById('edit_customer_name').value = customerName;
      document.getElementById('edit_phone').value = data.whatsapp || '';
      document.getElementById('edit_address').value = data.address || '';
      document.getElementById('edit_email').value = data.email || '';
      document.getElementById('edit_notes').value = data.notes || '';
      document.getElementById('edit_profile').value = data.profile_cobranca || 'AUTOMATICO';
      document.getElementById('editModal').classList.add('active');
      if (window.lucide) lucide.createIcons();
    })
    .catch(err => {
      console.error('Erro ao carregar dados:', err);
      alert('Erro ao carregar dados do cliente.');
    });
}

function closeEditModal() {
  document.getElementById('editModal').classList.remove('active');
  document.getElementById('editForm').reset();
}

// === Modal de Registro de Contato ===
function togglePromessaFields() {
  const outcome = document.getElementById('contact_outcome').value;
  const isPromessa = outcome === 'PROMESSA';
  document.getElementById('promessa-fields').style.display = isPromessa ? '' : 'none';
  document.getElementById('next-contact-field').style.display = isPromessa ? 'none' : '';
  document.getElementById('contact_promised_amount').required = isPromessa;
}

function openContactModal(customerId, customerName) {
  document.getElementById('contact_customer_id').value = customerId;
  document.getElementById('contact_customer_name').value = customerName;
  document.getElementById('contact_display_name').textContent = customerName;
  const d = new Date(); d.setDate(d.getDate() + 3);
  document.getElementById('contact_next_date').value = d.toISOString().split('T')[0];
  document.getElementById('contactModal').classList.add('active');
  togglePromessaFields();
  if (window.lucide) lucide.createIcons();
}

function closeContactModal() {
  document.getElementById('contactModal').classList.remove('active');
  document.getElementById('contactForm').reset();
  togglePromessaFields();
}

// === Sincronizar Clientes ERP ===
async function syncCustomers() {
  const btn = document.getElementById('sync-btn');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<i class="spin" data-lucide="loader-2"></i> Sincronizando...';
  if (window.lucide) lucide.createIcons();

  try {
    const resp = await fetch('/api/sync/customers', { method: 'POST', credentials: 'same-origin' });
    const data = await resp.json();
    if (resp.ok) {
      alert(`✅ Sincronização concluída!\n\nTotal processado: ${data.total}\nClientes novos: ${data.created}\nDados atualizados: ${data.updated}`);
      loadPriorityQueue();
    } else {
      alert('❌ Erro na sincronização: ' + (data.detail || 'Erro desconhecido'));
    }
  } catch (err) {
    console.error('Erro:', err);
    alert('❌ Erro de conexão ao sincronizar.');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
    if (window.lucide) lucide.createIcons();
  }
}

// === Modal da Agenda ===
function openAgendaModal() {
  document.getElementById('agendaModal').classList.add('active');
  if (window.lucide) lucide.createIcons();
}
function closeAgendaModal() {
  document.getElementById('agendaModal').classList.remove('active');
}

// === Modal de Reconciliação ===
function openReconModal() {
  document.getElementById('reconModal').classList.add('active');
  if (window.lucide) lucide.createIcons();
}
function closeReconModal() {
  document.getElementById('reconModal').classList.remove('active');
}

// === Inicialização ===
document.addEventListener('DOMContentLoaded', () => {
  initFunil();
  loadPriorityQueue(1);

  document.getElementById('editModal').addEventListener('click', e => {
    if (e.target.id === 'editModal') closeEditModal();
  });
  document.getElementById('editForm').addEventListener('submit', async e => {
    e.preventDefault();
    const customerId = document.getElementById('edit_customer_id').value;
    const data = {
      whatsapp: document.getElementById('edit_phone').value,
      address: document.getElementById('edit_address').value,
      email: document.getElementById('edit_email').value,
      notes: document.getElementById('edit_notes').value,
      profile_cobranca: document.getElementById('edit_profile').value
    };
    try {
      const resp = await fetch(`/api/customers/${customerId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        credentials: 'same-origin'
      });
      if (resp.ok) {
        closeEditModal();
        await loadPriorityQueue();
        alert('✅ Cadastro atualizado com sucesso!');
      } else {
        alert('❌ Erro ao atualizar cadastro.');
      }
    } catch (err) {
      console.error('Erro:', err);
      alert('❌ Erro ao atualizar cadastro.');
    }
  });

  document.getElementById('contactModal').addEventListener('click', e => {
    if (e.target.id === 'contactModal') closeContactModal();
  });
  document.getElementById('contactForm').addEventListener('submit', async e => {
    e.preventDefault();
    const outcome = document.getElementById('contact_outcome').value;
    const isPromessa = outcome === 'PROMESSA';
    const dateValue = isPromessa
      ? document.getElementById('contact_next_date').value
      : document.getElementById('contact_next_date_other').value;
    const payload = {
      customer_id: parseInt(document.getElementById('contact_customer_id').value),
      user_id: 0,
      action_type: document.getElementById('contact_type').value,
      outcome,
      promised_date: dateValue || null,
      notes: document.getElementById('contact_notes').value || null
    };
    if (isPromessa) {
      const amtRaw = document.getElementById('contact_promised_amount').value;
      if (!amtRaw || parseFloat(amtRaw) <= 0) {
        alert('⚠️ Informe o valor prometido para registrar uma Promessa de Pagamento.');
        return;
      }
      payload.promised_amount = parseFloat(amtRaw);
    }
    try {
      const resp = await fetch('/api/collection-actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin'
      });
      if (resp.ok) {
        closeContactModal();
        await loadPriorityQueue();
        alert('✅ Contato registrado com sucesso!');
      } else {
        let errMsg = 'Erro desconhecido';
        try { const errData = await resp.json(); errMsg = errData.detail || JSON.stringify(errData); } catch (_) {}
        alert('❌ Erro ao registrar contato:\n' + errMsg);
      }
    } catch (err) {
      console.error('Erro:', err);
      alert('❌ Erro de conexão ao registrar contato.');
    }
  });

  document.getElementById('agendaModal').addEventListener('click', e => {
    if (e.target.id === 'agendaModal') closeAgendaModal();
  });
  document.getElementById('reconModal').addEventListener('click', e => {
    if (e.target.id === 'reconModal') closeReconModal();
  });
});
