document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const extractBtn = document.getElementById('extract-btn');
  const validationToggle = document.getElementById('validation-toggle');
  
  const uploadSection = document.getElementById('upload-section');
  const processingSection = document.getElementById('processing-section');
  const resultSection = document.getElementById('result-section');
  
  const resetBtn = document.getElementById('reset-btn');
  const downloadLink = document.getElementById('download-link');
  const jsonOutput = document.getElementById('json-output');
  const toast = document.getElementById('toast');

  let currentFile = null;

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

      const result = await response.json();
      
      // Update and show results
      renderJsonResult(result);
      downloadLink.href = `/download/${result.file_id}`;
      
      switchSection(processingSection, resultSection);

    } catch (error) {
      console.error(error);
      showToast(error.message);
      switchSection(processingSection, uploadSection);
    }
  });

  resetBtn.addEventListener('click', () => {
    currentFile = null;
    fileInput.value = '';
    dropZone.querySelector('h3').textContent = 'Drag & Drop your invoice here';
    dropZone.querySelector('.file-hints').textContent = 'Supports JPG, PNG, PDF, and DOCX up to 10MB';
    extractBtn.disabled = true;
    switchSection(resultSection, uploadSection);
  });

  // --- Utilities --- //

  function switchSection(from, to) {
    from.classList.remove('active-section');
    setTimeout(() => {
      from.classList.add('hidden');
      to.classList.remove('hidden');
      // small delay to allow display:block to apply before animating opacity
      requestAnimationFrame(() => {
        to.classList.add('active-section');
      });
    }, 400); // matches CSS transition time
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.remove('hidden');
    // trigger reflow
    void toast.offsetWidth;
    toast.classList.add('show');
    
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.classList.add('hidden'), 300);
    }, 4000);
  }

  function renderJsonResult(jsonObj) {
    const jsonString = JSON.stringify(jsonObj, null, 2);
    jsonOutput.innerHTML = syntaxHighlight(jsonString);
  }

  function syntaxHighlight(json) {
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
        let cls = 'number';
        if (/^"/.test(match)) {
            if (/:$/.test(match)) {
                cls = 'key';
                // Remove the quote and colon for better styling optionally, 
                // but keeping it structural is safer.
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
