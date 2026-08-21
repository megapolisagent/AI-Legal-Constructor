// Drag-and-drop и вставка из буфера (Ctrl+V) для зоны загрузки фото/PDF (.scan-box).
// Выбранный любым способом файл сразу отправляет форму — так же, как обычный клик
// по кнопке "Распознать". Ничего не отправляется никуда, кроме локального сервера
// этого же приложения (см. README — Вариант A, данные не покидают компьютер).
(function () {
  function setFileAndSubmit(box, file) {
    const input = box.querySelector('input[type="file"]');
    const form = box.querySelector('form');
    if (!input || !form || !file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    form.submit();
  }

  function wireDropzone(box) {
    box.addEventListener('dragover', function (e) {
      e.preventDefault();
      box.classList.add('drag-over');
    });
    box.addEventListener('dragleave', function () {
      box.classList.remove('drag-over');
    });
    box.addEventListener('drop', function (e) {
      e.preventDefault();
      box.classList.remove('drag-over');
      if (e.dataTransfer.files.length) {
        setFileAndSubmit(box, e.dataTransfer.files[0]);
      }
    });
  }

  document.querySelectorAll('.scan-box').forEach(wireDropzone);

  // Вставка из буфера — один слушатель на страницу: на экране в моменте только
  // одна зона загрузки, поэтому вставляем в неё, без необходимости сначала кликать.
  document.addEventListener('paste', function (e) {
    const box = document.querySelector('.scan-box');
    if (!box) return;
    const items = (e.clipboardData || window.clipboardData).items;
    for (const item of items) {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) {
          setFileAndSubmit(box, file);
          break;
        }
      }
    }
  });
})();
