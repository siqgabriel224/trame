/* ES5 para mostrar um aviso inclusive em navegadores antigos do Windows 7. */
(function () {
  var compatible =
    window.Promise &&
    window.fetch &&
    window.Map &&
    window.HTMLDialogElement &&
    HTMLDialogElement.prototype.showModal &&
    window.crypto &&
    window.crypto.getRandomValues &&
    Object.fromEntries;
  if (!compatible) {
    document.body.className = 'login-page';
    document.body.innerHTML =
      '<main class="login-card"><h1>Atualize o navegador</h1><p>O Tramê precisa de Firefox ESR 115 ou Edge/Chrome 109 ou mais recente. Internet Explorer não é compatível.</p><p>Abra o Tramê em um desses navegadores. Seus dados continuam guardados neste computador.</p></main>';
    return;
  }
  if (!window.structuredClone)
    window.structuredClone = function (value) {
      return JSON.parse(JSON.stringify(value));
    };
  if (!window.crypto.randomUUID)
    window.crypto.randomUUID = function () {
      var bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 15) | 64;
      bytes[8] = (bytes[8] & 63) | 128;
      var hex = Array.prototype.map
        .call(bytes, function (b) {
          return ('0' + b.toString(16)).slice(-2);
        })
        .join('');
      return (
        hex.slice(0, 8) +
        '-' +
        hex.slice(8, 12) +
        '-' +
        hex.slice(12, 16) +
        '-' +
        hex.slice(16, 20) +
        '-' +
        hex.slice(20)
      );
    };
})();
