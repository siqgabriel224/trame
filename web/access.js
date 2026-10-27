'use strict';
const TrameAccess = { session: null, ready: null };
TrameAccess.request = async (path, data) => {
  const r = await fetch(path, {
    ...(data === undefined
      ? {}
      : {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': TrameAccess.session?.csrf || '',
          },
          body: JSON.stringify(data),
        }),
  });
  const d = await r.json();
  if (r.status === 401) {
    document.querySelector('#sessionExpired')?.removeAttribute('hidden');
    throw Error(
      'Sua sessão terminou. Entre novamente em outra aba e tente salvar de novo. Seu formulário foi mantido.'
    );
  }
  if (!r.ok)
    throw Object.assign(Error(d.error || 'Falha ao conectar ao servidor.'), { status: r.status });
  return d;
};
TrameAccess.changes = (before, after) => {
  const result = [];
  for (const key of ['orders', 'clients', 'employees', 'stock', 'reservations']) {
    const old = new Map((before[key] || []).map((r) => [r.id, r]));
    for (const row of after[key] || []) {
      const prior = old.get(row.id) || null;
      if (JSON.stringify(prior) !== JSON.stringify(row))
        result.push({ key, id: row.id, before: prior, after: row });
    }
    if ((before[key] || []).some((r) => !(after[key] || []).some((n) => n.id === r.id)))
      throw Error('Não é permitido excluir registros.');
  }
  for (const key of ['company', 'warningDays'])
    if (JSON.stringify(before[key]) !== JSON.stringify(after[key]))
      result.push({ key, before: before[key], after: after[key] });
  return result;
};
TrameAccess.permissions = () => {
  if (!TrameAccess.session) return;
  const admin = TrameAccess.session.user.role === 'admin';
  for (const id of ['companyButton', 'export', 'warningDays']) {
    const e = document.getElementById(id);
    if (e) e.disabled = !admin;
  }
  if (!admin)
    document
      .querySelectorAll('[data-action="new-employee"],[data-action="edit-employee"]')
      .forEach((e) => (e.disabled = true));
};
TrameAccess.refreshSession = async () => {
  const r = await fetch('/api/session'),
    s = await r.json();
  if (!s.user || s.user.mustChangePassword) {
    document.querySelector('#sessionExpired')?.removeAttribute('hidden');
    throw Error('Entre novamente em outra aba e volte para salvar. Seu formulário foi mantido.');
  }
  TrameAccess.session = s;
  const name = document.querySelector('#signedUser');
  if (name) name.textContent = s.user.name;
  document.querySelector('#sessionExpired')?.setAttribute('hidden', '');
  return s;
};
TrameAccess.ready = TrameAccess.refreshSession()
  .then((s) => {
    if (!document.querySelector('main>header')) return s;
    const header = document.querySelector('main>header');
    header.insertAdjacentHTML(
      'beforeend',
      '<div class="account-bar"><span id="signedUser" class="account-name"></span><button id="myAccount" class="secondary">Minha conta</button><button id="signOut" class="secondary">Sair</button></div>'
    );
    document.querySelector('#signedUser').textContent = s.user.name;
    document.querySelector('#signOut').onclick = async () => {
      try {
        await TrameAccess.request('/api/logout', {});
        location.replace('/login');
      } catch (e) {
        toast(e.message, true);
      }
    };
    document.querySelector('#myAccount').onclick = openAccount;
    document.body.insertAdjacentHTML(
      'beforeend',
      '<div id="sessionExpired" class="session-banner" hidden>Sua sessão terminou. <a href="/login" target="_blank" rel="noopener">Entrar novamente</a>. Depois retorne a esta aba para salvar suas alterações.</div><dialog id="accountDialog" class="wide"><div id="accountContent"></div></dialog>'
    );
    TrameAccess.permissions();
    let touched = Date.now();
    for (const event of ['pointerdown', 'keydown'])
      document.addEventListener(
        event,
        (e) => {
          if (e.isTrusted && Date.now() - touched > 120000) {
            touched = Date.now();
            TrameAccess.request('/api/activity', {}).catch(() => {});
          }
        },
        true
      );
    return s;
  })
  .catch((e) => {
    if (location.pathname === '/')
      location.replace('/login?next=' + encodeURIComponent(location.pathname + location.search));
    return null;
  });
async function openAccount() {
  const d = document.querySelector('#accountDialog');
  d.showModal();
  await accountHome();
}
function accountShell(title, body) {
  const root = document.querySelector('#accountContent');
  root.innerHTML = `<div class="modal-top"><h2>${esc(title)}</h2><button type="button" id="closeAccount" class="icon" aria-label="Fechar minha conta">×</button></div>${body}<p id="accountError" class="account-error" role="status"></p>`;
  document.querySelector('#closeAccount').onclick = () =>
    document.querySelector('#accountDialog').close();
}
async function accountHome() {
  const u = TrameAccess.session.user;
  accountShell(
    'Minha conta',
    `<p class="notes">${esc(u.name)} · ${esc(u.username)} · ${u.role === 'admin' ? 'Administrador' : 'Funcionário'}</p><div class="detail-actions"><a class="secondary" href="/login?change=1">Trocar minha senha</a>${u.role === 'admin' ? '<button class="primary" id="manageAccounts">Acessos dos funcionários</button><button class="secondary" id="showAudit">Histórico de ações</button>' : ''}</div><p class="hint">Sua conta é individual. Saia ao terminar de usar um computador compartilhado.</p>`
  );
  document.querySelector('#manageAccounts')?.addEventListener('click', accountUsers);
  document.querySelector('#showAudit')?.addEventListener('click', accountAudit);
}
async function accountUsers() {
  try {
    const users = await TrameAccess.request('/api/users');
    accountShell(
      'Acessos dos funcionários',
      `<p class="notes">Funcionários podem consultar e operar pedidos, orçamentos, pagamentos, produção, entregas, clientes e estoque. Administradores também gerenciam contas, funcionários e configurações.</p><button id="createAccount" class="primary">＋ Criar acesso</button><div class="account-list">${users.map((u) => `<article class="account-person"><div><strong>${esc(u.name)}</strong><small>${esc(u.username)} · ${u.role === 'admin' ? 'Administrador' : 'Funcionário'} · ${u.active ? 'Ativo' : 'Desativado'}${u.mustChangePassword ? ' · Troca de senha pendente' : ''}</small></div><button class="secondary" data-account="${esc(u.id)}">Gerenciar acesso</button></article>`).join('')}</div>`
    );
    document.querySelector('#createAccount').onclick = () => accountForm();
    document
      .querySelectorAll('[data-account]')
      .forEach(
        (b) => (b.onclick = () => accountForm(users.find((u) => u.id === b.dataset.account)))
      );
  } catch (e) {
    document.querySelector('#accountError').textContent = e.message;
  }
}
function accountForm(user = null) {
  const employees =
    typeof state !== 'undefined' && state ? state.employees.filter((e) => e.active) : [];
  accountShell(
    user ? 'Gerenciar acesso' : 'Criar acesso',
    `<form id="accountForm" class="form-grid">${!user ? '<label>Nome<input name="name" required maxlength="150" autocomplete="off"></label><label>Login<input name="username" required minlength="3" maxlength="60" pattern="[a-zA-Z0-9._-]+" autocomplete="off"></label><label class="full">Vincular ao funcionário<select name="employeeId"><option value="">Sem vínculo</option>' + employees.map((e) => `<option value="${esc(e.id)}">${esc(e.name)}</option>`).join('') + '</select></label>' : `<p class="full notes">${esc(user.name)} · ${esc(user.username)}</p>`}<label>Perfil<select name="role"><option value="employee">Funcionário</option><option value="admin">Administrador</option></select></label>${user ? '<label>Situação<select name="active"><option value="true">Ativo</option><option value="false">Desativado</option></select></label>' : ''}<label class="full">${user ? 'Nova senha temporária (opcional)' : 'Senha temporária'}<input name="password" type="password" autocomplete="new-password" minlength="12" maxlength="128" ${user ? '' : 'required'}></label><p class="hint full">Ao criar ou redefinir a senha, a pessoa precisará trocá-la no próximo acesso. Alterar uma conta encerra suas sessões abertas.</p><div class="modal-actions full"><button type="button" class="secondary" id="cancelAccountForm">Voltar</button><button class="primary">Salvar acesso</button></div></form>`
  );
  const f = document.querySelector('#accountForm');
  if (user) {
    f.elements.role.value = user.role;
    f.elements.active.value = String(user.active);
  }
  f.elements.employeeId?.addEventListener('change', () => {
    const e = employees.find((e) => e.id === f.elements.employeeId.value);
    if (e) f.elements.name.value = e.name;
  });
  document.querySelector('#cancelAccountForm').onclick = accountUsers;
  f.onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(f));
    if (user) {
      data.id = user.id;
      data.active = data.active === 'true';
    }
    const b = f.querySelector('button.primary');
    b.disabled = true;
    try {
      await TrameAccess.request('/api/users/' + (user ? 'update' : 'create'), data);
      f.reset();
      await accountUsers();
    } catch (err) {
      document.querySelector('#accountError').textContent = err.message;
      b.disabled = false;
    }
  };
}
async function accountAudit() {
  try {
    const rows = await TrameAccess.request('/api/audit');
    accountShell(
      'Histórico de ações',
      `<p class="hint">Últimas 100 ações registradas no servidor. Os horários abaixo usam o fuso deste computador.</p><ul class="audit-list">${rows.map((r) => `<li><strong>${esc(r.name)}</strong> · ${esc(r.action)}<small>${new Date(r.at * 1000).toLocaleString('pt-BR')} · ${esc(r.details)}</small></li>`).join('')}</ul>`
    );
  } catch (e) {
    document.querySelector('#accountError').textContent = e.message;
  }
}
