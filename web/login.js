'use strict';
let loginSession;
const field = (id) => document.getElementById(id);
const message = (text) => {
  field('loginMessage').textContent = text;
};
if (new URLSearchParams(location.search).get('deleted') === '1')
  message('Sua conta foi excluída. O acesso foi encerrado em todos os dispositivos.');
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
  if (!r.ok) throw Object.assign(Error(d.error), { emailPending: d.emailPending });
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
        emailConfirmationMode(data.email);
        message(
          'Cadastro criado. Enviamos um código para confirmar seu e-mail antes de ativar o acesso.'
        );
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
      if (id === 'setupForm' && err.emailPending) {
        form.reset();
        emailConfirmationMode(data.email);
      }
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
    if (s.demonstration) {
      const notice = document.createElement('p');
      notice.className = 'login-demo';
      notice.textContent =
        'Demonstração com dados fictícios. Login: demo · Senha: Trame-Demo-2026!';
      field('loginIntro').after(notice);
    }
    if (s.setupNeeded) {
      field('loginForm').hidden = true;
      field('setupForm').hidden = false;
      field('loginTitle').textContent = 'Primeiro acesso';
      field('loginIntro').textContent =
        'Neste computador, abra o arquivo dados/chave-primeiro-acesso.txt e use a chave abaixo para criar o administrador. Não compartilhe esse arquivo.';
      field('loginHelp').textContent =
        'Depois, cadastre os acessos dos funcionários em Minha conta → Acessos.';
      if (s.emailDelivery?.configured === false) {
        field('setupForm').querySelector('button[type="submit"]').disabled = true;
        message(
          'Antes de criar o administrador, configure a conta de envio de e-mail no servidor. Consulte o guia de cadastro por e-mail na pasta docs. Depois reinicie o Tramê e reabra esta tela.'
        );
      }
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

function recoveryMode(reset = false) {
  for (const id of ['loginForm', 'setupForm', 'passwordForm', 'loginHelp']) field(id).hidden = true;
  field('recoveryForm').hidden = reset;
  field('resetForm').hidden = !reset;
  field('loginTitle').textContent = reset ? 'Redefinir senha' : 'Recuperar senha';
  field('loginIntro').textContent = reset
    ? 'Informe o código enviado ao seu e-mail e escolha uma nova senha.'
    : 'Enviaremos um código para o e-mail cadastrado. Ele vale por 15 minutos.';
}
field('forgotPassword').onclick = () => {
  message('');
  recoveryMode();
};
field('haveCode').onclick = () => recoveryMode(true);
for (const id of ['recoveryForm', 'resetForm'])
  field(id).onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target,
      data = Object.fromEntries(new FormData(form)),
      button = form.querySelector('button[type="submit"]');
    if (id === 'resetForm' && data.confirm !== data.newPassword)
      return message('As senhas não conferem.');
    button.disabled = true;
    message('');
    try {
      const result = await authRequest(
        id === 'resetForm' ? '/api/reset-password' : '/api/forgot-password',
        data
      );
      if (id === 'resetForm') {
        form.reset();
        location.replace('/login');
      } else {
        field('resetForm').elements.email.value = data.email;
        recoveryMode(true);
        message(result.message);
      }
    } catch (err) {
      message(err.message);
    } finally {
      button.disabled = false;
    }
  };

function emailConfirmationMode(email = '') {
  for (const id of [
    'loginForm',
    'setupForm',
    'passwordForm',
    'recoveryForm',
    'resetForm',
    'loginHelp',
  ])
    field(id).hidden = true;
  field('emailConfirmationForm').hidden = false;
  field('emailConfirmationForm').elements.email.value = email;
  field('loginTitle').textContent = 'Confirme seu e-mail';
  field('loginIntro').textContent =
    'Use o código enviado ao seu e-mail para ativar sua conta. Ele vale por 15 minutos. Confira também o spam.';
}
field('openEmailConfirmation').onclick = () => {
  message('');
  emailConfirmationMode();
};
field('emailConfirmationForm').onsubmit = async (e) => {
  e.preventDefault();
  const form = e.target,
    button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await authRequest('/api/email/confirm', Object.fromEntries(new FormData(form)));
    location.replace('/login?verified=1');
  } catch (err) {
    message(err.message);
  } finally {
    button.disabled = false;
  }
};
field('resendEmailCode').onclick = async (e) => {
  const form = field('emailConfirmationForm');
  if (!form.elements.email.reportValidity()) return;
  const button = e.currentTarget;
  button.disabled = true;
  try {
    const result = await authRequest('/api/email/resend', { email: form.elements.email.value });
    message(result.message);
  } catch (err) {
    message(err.message);
  } finally {
    button.disabled = false;
  }
};
if (new URLSearchParams(location.search).get('verified') === '1')
  message('E-mail confirmado! Sua conta está ativa. Entre com sua senha.');
