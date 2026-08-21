// Drag-and-drop и вставка из буфера (Ctrl+V) для зоны загрузки фото/PDF (.scan-box).
// Файл, выбранный любым способом, кладётся в обычный <input type="file"> и явно
// показывается пользователю ("Выбран файл: ...") — нажимать «Распознать» всё равно
// нужно самому. Без этой видимой подписи было непонятно, действительно ли файл
// прикрепился, и что делать дальше (владелец, 2026-08-21).
(function () {
  function setFile(box, file) {
    const input = box.querySelector('input[type="file"]');
    const status = box.querySelector('.file-status');
    if (!input || !file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    if (status) {
      status.textContent = 'Выбран файл: ' + file.name + ' — нажмите «Распознать»';
    }
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
        setFile(box, e.dataTransfer.files[0]);
      }
    });
  }

  document.querySelectorAll('.scan-box').forEach(wireDropzone);

  // Вставка из буфера — один слушатель на страницу: на экране в моменте только
  // одна зона загрузки, поэтому вставляем в неё без необходимости сначала кликать.
  document.addEventListener('paste', function (e) {
    const box = document.querySelector('.scan-box');
    if (!box) return;
    const items = (e.clipboardData || window.clipboardData).items;
    for (const item of items) {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) {
          setFile(box, file);
          break;
        }
      }
    }
  });
})();
