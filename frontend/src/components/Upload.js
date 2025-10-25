import React, { useState } from 'react';
import axios from 'axios';
import './Upload.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Upload({ onUpload }) {
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFiles(e.target.files);
    }
  };

  const handleFiles = (fileList) => {
    const newFiles = Array.from(fileList);
    setFiles(prev => [...prev, ...newFiles]);
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const uploadFiles = async () => {
    if (files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
      // Let axios set the Content-Type header (it will include the multipart boundary)
      const response = await axios.post(
        `${API_URL}/api/v1/documents/upload`,
        formData
      );

  alert(response.data.message);
  // pass both the returned ids and the original File objects so the caller
  // can show the original filenames immediately (the backend list may
  // not yet include the new documents while they are processing)
  onUpload(response.data.document_ids, files);
      setFiles([]);
    } catch (error) {
      alert('Erro ao fazer upload: ' + error.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-container">
      <h2>📤 Upload de Documentos Fiscais</h2>

      <div 
        className={`drop-zone ${dragActive ? 'active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="file-upload"
          multiple
          accept=".pdf,.xml,.png,.jpg,.jpeg"
          onChange={handleChange}
          style={{ display: 'none' }}
        />
        <label htmlFor="file-upload" className="file-label">
          <div className="upload-icon">📁</div>
          <p className="upload-text">
            Arraste arquivos aqui ou <span className="browse">clique para selecionar</span>
          </p>
          <p className="upload-hint">
            Suporta: PDF, XML, PNG, JPG (NF-e, NFC-e, CT-e, Cupons)
          </p>
        </label>
      </div>

      {files.length > 0 && (
        <div className="files-list">
          <h3>📋 Arquivos Selecionados ({files.length})</h3>
          {files.map((file, index) => (
            <div key={index} className="file-item">
              <div className="file-info">
                <span className="file-icon">📄</span>
                <div>
                  <div className="file-name">{file.name}</div>
                  <div className="file-size">{(file.size / 1024).toFixed(2)} KB</div>
                </div>
              </div>
              <button onClick={() => removeFile(index)} className="remove-btn">
                ✕
              </button>
            </div>
          ))}

          <button 
            onClick={uploadFiles} 
            disabled={uploading}
            className="upload-btn"
          >
            {uploading ? '⏳ Processando...' : '🚀 Processar Documentos'}
          </button>
        </div>
      )}
    </div>
  );
}

export default Upload;
