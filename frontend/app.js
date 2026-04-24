document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const extractBtn = document.getElementById('extract-btn');
  const validationToggle = document.getElementById('validation-toggle');
  
  const uploadSection = document.getElementById('upload-section');
  const processingSection = document.getElementById('processing-section');
  const resultSection = document.getElementById('result-section');
  
  const resetBtn = document.getElementById('reset-btn');
  const downloadRawBtn = document.getElementById('download-raw');
  const jsonOutput = document.getElementById('json-output');
  const toast = document.getElementById('toast');

  let currentFile = null;
  let currentResult = null;

  // --- Drag and Drop Handling --- //

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
      dropZone.classList.add('drag-over');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
      dropZone.classList.remove('drag-over');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
  });

  fileInput.addEventListener('change', function() {
    handleFiles(this.files);
  });

  function handleFiles(files) {
    if (files.length > 0) {
      currentFile = files[0];
      // Update UI
      dropZone.querySelector('h3').textContent = currentFile.name;
      dropZone.querySelector('.file-hints').textContent = `Size: ${(currentFile.size / (1024 * 1024)).toFixed(2)} MB`;
      extractBtn.disabled = false;
    }
  }

  // --- API Interaction --- //

  extractBtn.addEventListener('click', async () => {
    if (!currentFile) return;

    // Switch to processing state
    switchSection(uploadSection, processingSection);
    
    const formData = new FormData();
    formData.append('file', currentFile);
    formData.append('enable_validation', validationToggle.checked);

    try {
      const response = await fetch('/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }

      currentResult = await response.json();
      
      // Update results
      renderRawJson(currentResult);
      
      switchSection(processingSection, resultSection);

    } catch (error) {
      console.error(error);
      showToast(error.message);
      switchSection(processingSection, uploadSection);
    }
  });

  resetBtn.addEventListener('click', () => {
    currentFile = null;
    currentResult = null;
    fileInput.value = '';
    dropZone.querySelector('h3').textContent = 'Drag & Drop your document here';
    dropZone.querySelector('.file-hints').textContent = 'Supports JPG, PNG, PDF, and DOCX up to 10MB';
    extractBtn.disabled = true;
    switchSection(resultSection, uploadSection);
  });

  downloadRawBtn.addEventListener('click', () => {
    if (!currentResult) return;
    const docType = currentResult.document_type || 'document';
    downloadJson(currentResult, `${docType}_full_${currentResult.file_id}.json`);
  });

  // --- Rendering --- //

  function renderRawJson(jsonObj) {
    const jsonString = JSON.stringify(jsonObj, null, 2);
    jsonOutput.innerHTML = syntaxHighlight(jsonString);
  }

  // --- Utilities --- //

  function switchSection(from, to) {
    from.classList.remove('active-section');
    setTimeout(() => {
      from.classList.add('hidden');
      to.classList.remove('hidden');
      requestAnimationFrame(() => {
        to.classList.add('active-section');
      });
    }, 400);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    void toast.offsetWidth;
    toast.classList.add('show');
    
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.classList.add('hidden'), 300);
    }, 4000);
  }

  function downloadJson(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
            } else {
                cls = 'string';
            }
        } else if (/true|false/.test(match)) {
            cls = 'boolean';
        } else if (/null/.test(match)) {
            cls = 'null';
        }
        return '<span class="' + cls + '">' + match + '</span>';
    });
  }

});
