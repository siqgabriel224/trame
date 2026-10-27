'use strict';
let loginSession;
const field = (id) => document.getElementById(id);
const message = (text) => {
  field('loginMessage').textContent = text;
};
const destination = () => {
  const next = new URLSearchParams(location.search).get('next') || '/';
  if (!next.startsWith('/') || next.startsWith('//') || /[\\\u0000-\u0020]/.test(next)) return '/';
  const target = new URL(next, location.origin);
  if (target.origin !== location.origin || target.pathname.startsWith('/login')) return '/';
  return target.pathname + target.search + target.hash;
};
async function authRequest(path, data) {
  const r = await fetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(loginSession?.csrf ? { 'X-CSRF-Token': loginSession.csrf } : {}),
    },
    body: JSON.stringify(data),
  });
  const d = await r.json();
  if (!r.ok) throw Error(d.error);
  return d;
}
function changeMode() {
  field('loginForm').hidden = true;
  field('setupForm').hidden = true;
  field('passwordForm').hidden = false;
  field('loginTitle').textContent = 'Defina sua senha';
  field('loginIntro').textContent =
    'Use uma senha pessoal com pelo menos 12 caracteres. Depois entre novamente.';
  field('loginHelp').hidden = true;
}
for (const id of ['loginForm', 'setupForm', 'passwordForm'])
  field(id).onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target,
      data = Object.fromEntries(new FormData(form)),
      button = form.querySelector('button[type="submit"]');
    if (data.confirm !== undefined && data.confirm !== (data.newPassword || data.password))
      return message('As senhas não conferem.');
    button.disabled = true;
    message('');
    try {
      if (id === 'setupForm') {
        await authRequest('/api/setup', data);
        form.reset();
        field('setupForm').hidden = true;
        field('loginForm').hidden = false;
        field('loginTitle').textContent = 'Entre na sua conta';
        field('loginIntro').textContent =
          'Administrador criado. Entre com o login e a senha que você definiu.';
      } else if (id === 'passwordForm') {
        await authRequest('/api/password', data);
        location.replace('/login');
      } else {
        loginSession = await authRequest('/api/login', data);
        form.reset();
        if (loginSession.user.mustChangePassword) changeMode();
        else location.replace(destination());
      }
    } catch (err) {
      message(err.message);
    } finally {
      button.disabled = false;
    }
  };
field('cancelPassword').onclick = async () => {
  try {
    await authRequest('/api/logout', {});
    location.replace('/login');
  } catch (err) {
    message(err.message);
  }
};
fetch('/api/session')
  .then((r) => r.json())
  .then((s) => {
    loginSession = s;
    if (s.setupNeeded) {
      field('loginForm').hidden = true;
      field('setupForm').hidden = false;
      field('loginTitle').textContent = 'Primeiro acesso';
      field('loginIntro').textContent =
        'Neste computador, abra o arquivo dados/chave-primeiro-acesso.txt e use a chave abaixo para criar o administrador. Não compartilhe esse arquivo.';
      field('loginHelp').textContent =
        'Depois, cadastre os acessos dos funcionários em Minha conta → Acessos.';
    } else if (
      s.user?.mustChangePassword ||
      (s.user && new URLSearchParams(location.search).get('change') === '1')
    ) {
      changeMode();
    } else if (s.user) {
      location.replace(destination());
    }
  })
  .catch(() => message('Não foi possível conectar ao servidor. Confira se ele está ligado.'));
