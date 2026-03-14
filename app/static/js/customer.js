// customer.js — Lógica da página de detalhe do cliente

async function toggleMsgs(customerId, atualAtivo) {
  const btn = document.getElementById('btnToggleMsgs');
  btn.disabled = true;
  try {
    const res = await fetch(`/customers/${customerId}/toggle-msgs`, { method: 'POST' });
    if (res.ok) window.location.reload();
    else btn.disabled = false;
  } catch (e) {
    btn.disabled = false;
  }
}

async function startEdit(container) {
  const field = container.dataset.field;
  let currentVal = container.dataset.val;
  const span = container.querySelector('.display-span');
  const icon = container.querySelector('.edit-icon');

  if (container.querySelector('input')) return;

  const originalOnClick = container.onclick;
  container.onclick = null;
  icon.style.opacity = '0';

  const input = document.createElement('input');
  input.type = 'text';
  input.value = currentVal;
  input.className = 'inline-input';

  span.style.display = 'none';
  container.appendChild(input);
  input.focus();

  const finish = async (save) => {
    const newVal = input.value.trim();
    input.remove();
    span.style.display = 'inline';
    icon.style.opacity = '';

    if (save && newVal !== currentVal) {
      const oldText = span.innerText;
      span.innerText = "Salvando...";
      try {
        const res = await fetch(`/api/customers/${window.CUSTOMER_ID}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [field]: newVal })
        });
        const data = await res.json();
        if (data.success) {
          span.innerText = newVal || "Clique para adicionar";
          container.dataset.val = newVal;
          currentVal = newVal;
        } else {
          alert("Erro ao salvar: " + data.message);
          span.innerText = oldText;
        }
      } catch (err) {
        alert("Erro de conexão");
        span.innerText = oldText;
      }
    } else {
      span.innerText = currentVal || "Clique para adicionar";
    }

    setTimeout(() => { container.onclick = originalOnClick; }, 100);
  };

  input.onblur = () => finish(true);
  input.onkeydown = (e) => {
    if (e.key === 'Enter') finish(true);
    if (e.key === 'Escape') finish(false);
  };
}

async function salvarPerfilDevedor(customerId, valor) {
  try {
    const res = await fetch(`/api/customers/${customerId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ perfil_devedor: valor })
    });
    const data = await res.json();
    if (!data.success) alert('Erro ao salvar perfil: ' + data.message);
  } catch (err) {
    alert('Erro de conexão ao salvar perfil');
  }
}

// === Acordos ===
async function loadAcordos() {
  const el = document.getElementById('acordos-list-customer');
  try {
    const res = await fetch(`/api/acordos?customer_id=${window.CUSTOMER_ID}`);
    const data = await res.json();
    if (!data.length) {
      el.innerHTML = '<div class="muted small">Nenhum acordo registrado.</div>';
      return;
    }
    const statusColors = { ATIVO:'#d97706', CUMPRIDO:'#16a34a', QUEBRADO:'#dc2626' };
    const statusEmoji = { ATIVO:'🟡', CUMPRIDO:'✅', QUEBRADO:'❌' };
    el.innerHTML = '';
    data.forEach(a => {
      const cor = statusColors[a.status] || '#6b7280';
      const emoji = statusEmoji[a.status] || '•';
      const fmtBrl = v => Number(v||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
      const div = document.createElement('div');
      div.style.cssText = 'border:1px solid var(--border); border-radius:8px; padding:12px 14px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:flex-start;';
      div.innerHTML = `
        <div>
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            <span style="font-weight:700;">${fmtBrl(a.valor_acordado)}</span>
            <span style="font-size:11px; font-weight:600; padding:2px 8px; border-radius:10px; background:${cor}20; color:${cor};">${emoji} ${a.status}</span>
          </div>
          <div class="muted small">Original: ${fmtBrl(a.valor_original)} ${a.desconto_pct ? `· ${a.desconto_pct}% desconto` : ''} · ${a.forma_pagamento}</div>
          <div class="muted small">Prazo: ${a.novo_prazo} · Acordo: ${a.data_acordo}</div>
          ${a.notas ? `<div class="muted small" style="font-style:italic; margin-top:4px;">"${a.notas}"</div>` : ''}
        </div>
        <div style="display:flex; flex-direction:column; gap:4px; margin-left:10px;">
          ${a.status === 'ATIVO' ? `
            <button onclick="updateAcordo(${a.id},'CUMPRIDO')" class="btn small primary" style="font-size:11px; padding:4px 8px;">✅ Cumpriu</button>
            <button onclick="updateAcordo(${a.id},'QUEBRADO')" class="btn small danger" style="font-size:11px; padding:4px 8px;">❌ Quebrou</button>
          ` : ''}
        </div>`;
      el.appendChild(div);
    });
  } catch(e) {
    el.innerHTML = '<div style="color:var(--danger); font-size:13px;">Erro ao carregar acordos.</div>';
  }
}

async function updateAcordo(id, status) {
  try {
    const res = await fetch(`/api/acordos/${id}/status`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({status})
    });
    if (res.ok) loadAcordos();
    else alert('Erro ao atualizar acordo.');
  } catch { alert('Erro de conexão.'); }
}

function calcAcordo() {
  const orig = parseFloat(document.getElementById('ac_valor_original').value) || 0;
  const desc = parseFloat(document.getElementById('ac_desconto').value) || 0;
  document.getElementById('ac_valor_acordado').value = (orig * (1 - desc/100)).toFixed(2);
}

function openAcordoModal() {
  const today = new Date().toISOString().split('T')[0];
  const next30 = new Date(Date.now()+30*86400000).toISOString().split('T')[0];
  document.getElementById('ac_data').value = today;
  document.getElementById('ac_prazo').value = next30;
  document.getElementById('modalAcordo').style.display = 'flex';
}

function closeAcordoModal() {
  document.getElementById('modalAcordo').style.display = 'none';
  document.getElementById('formAcordo').reset();
}

async function saveAcordo(e) {
  e.preventDefault();
  const payload = {
    customer_id: window.CUSTOMER_ID,
    valor_original: parseFloat(document.getElementById('ac_valor_original').value),
    desconto_pct: parseFloat(document.getElementById('ac_desconto').value) || null,
    valor_acordado: parseFloat(document.getElementById('ac_valor_acordado').value),
    data_acordo: document.getElementById('ac_data').value,
    novo_prazo: document.getElementById('ac_prazo').value,
    forma_pagamento: document.getElementById('ac_forma').value,
    notas: document.getElementById('ac_notas').value || null
  };
  try {
    const res = await fetch('/api/acordos', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (res.ok) { closeAcordoModal(); loadAcordos(); alert('✅ Acordo registrado!'); }
    else { const d = await res.json(); alert('Erro: ' + (d.detail||'Falha ao salvar')); }
  } catch { alert('Erro de conexão.'); }
}

// === Modal Registrar Contato ===
function toggleCtFields() {
  const isPromessa = document.getElementById('ct_outcome').value === 'PROMESSA';
  document.getElementById('ct_promessa_fields').style.display = isPromessa ? '' : 'none';
  document.getElementById('ct_next_fields').style.display = isPromessa ? 'none' : '';
  document.getElementById('ct_amount').required = isPromessa;
}

function abrirModalContato() {
  const d = new Date(); d.setDate(d.getDate() + 3);
  const iso = d.toISOString().split('T')[0];
  document.getElementById('ct_date').value = iso;
  document.getElementById('ct_next_date').value = iso;
  document.getElementById('contatoModal').classList.add('active');
  toggleCtFields();
  if (window.lucide) lucide.createIcons();
}

function fecharModalContato() {
  document.getElementById('contatoModal').classList.remove('active');
  document.getElementById('contatoForm').reset();
  toggleCtFields();
}

// === Inicialização ===
document.addEventListener('DOMContentLoaded', () => {
  loadAcordos();

  document.getElementById('modalAcordo').addEventListener('click', e => {
    if (e.target.id === 'modalAcordo') closeAcordoModal();
  });

  document.getElementById('contatoModal').addEventListener('click', e => {
    if (e.target.id === 'contatoModal') fecharModalContato();
  });

  document.getElementById('contatoForm').addEventListener('submit', async e => {
    e.preventDefault();
    const outcome = document.getElementById('ct_outcome').value;
    const isPromessa = outcome === 'PROMESSA';
    const dateVal = isPromessa
      ? document.getElementById('ct_date').value
      : document.getElementById('ct_next_date').value;
    const payload = {
      customer_id: parseInt(document.getElementById('ct_customer_id').value),
      user_id: 0,
      action_type: document.getElementById('ct_type').value,
      outcome,
      promised_date: dateVal || null,
      notes: document.getElementById('ct_notes').value || null
    };
    if (isPromessa) {
      const amt = parseFloat(document.getElementById('ct_amount').value);
      if (!amt || amt <= 0) { alert('Informe o valor prometido.'); return; }
      payload.promised_amount = amt;
    }
    try {
      const res = await fetch('/api/collection-actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        credentials: 'same-origin'
      });
      if (res.ok) { fecharModalContato(); window.location.reload(); }
      else alert('Erro ao salvar contato.');
    } catch { alert('Erro de conexão.'); }
  });
});
