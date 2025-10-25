import React, { useState } from 'react';
import axios from 'axios';
import './App.css';
import Dashboard from './components/Dashboard';
import Upload from './components/Upload';
import ProcessingView from './components/ProcessingViewFixed';
import ProcessingHistory from './components/ProcessingHistory';

function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [uploadedDocs, setUploadedDocs] = useState([]);

  const openProcessing = (doc) => {
    // set uploadedDocs to a single-entry list so ProcessingView uses it as selected doc
    // accept either a full doc object or just an id
    if (doc && doc.id && doc.filename) setUploadedDocs([{ id: doc.id, filename: doc.filename, uploaded_at: doc.uploaded_at }]);
    else if (doc && doc.id) setUploadedDocs([{ id: doc.id, filename: doc.id, uploaded_at: doc.uploaded_at }]);
    setCurrentView('processing');
  };

  // docs: array of ids or full objects
  // files: optional array of File objects from the upload component so we can
  // show filenames immediately while the backend processes the documents
  const handleUpload = async (docs, files = []) => {
    // `docs` can be an array of document ids returned by the upload endpoint
    // Resolve them to full metadata via the list endpoint so ProcessingView receives filename/uploaded_at
    try {
      if (!docs || !docs.length) {
        setUploadedDocs([]);
        setCurrentView('processing');
        return;
      }
      // if items look like objects already, pass through
      const areObjects = docs.every(d => typeof d === 'object' && d !== null && d.id && d.filename);
      if (areObjects) {
        setUploadedDocs(docs);
        setCurrentView('processing');
        return;
      }

      const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const res = await axios.get(`${API_URL}/api/v1/documents`);
      const list = res.data?.documents || [];
      // map ids to full objects when possible; if the backend list doesn't
      // yet contain the new ids (processing delay), fall back to the
      // original File.name provided by the upload component (by index).
      const resolved = docs.map((id, idx) => {
        const found = list.find(d => d.id === id);
        if (found) return found;
        const fileObj = Array.isArray(files) && files[idx] ? files[idx] : null;
        const filename = fileObj ? (fileObj.name || id) : id;
        return { id, filename, uploaded_at: '' };
      });
      setUploadedDocs(resolved);
      setCurrentView('processing');
    } catch (e) {
      // fallback: set ids as-is (component will display ids as filenames)
      console.warn('Could not resolve uploaded docs metadata, falling back to ids', e?.message || e);
      // If files array is provided, use file names for immediate UX
      const fallback = (Array.isArray(docs) ? docs : []).map((d, idx) => {
        if (typeof d === 'object' && d !== null) return d;
        const fileObj = Array.isArray(files) && files[idx] ? files[idx] : null;
        return { id: d, filename: fileObj ? fileObj.name : d };
      });
      setUploadedDocs(fallback);
      setCurrentView('processing');
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="header-content">
          <h1>📊 Sistema de Extração Fiscal</h1>
          <p>Extração Inteligente com Agentes de IA</p>
        </div>
        <nav className="nav-buttons">
          <button onClick={() => setCurrentView('dashboard')} 
                  className={currentView === 'dashboard' ? 'active' : ''}>
            Dashboard
          </button>
          <button onClick={() => setCurrentView('history')}
                  className={currentView === 'history' ? 'active' : ''}>
            Histórico
          </button>
          <button onClick={() => setCurrentView('upload')}
                  className={currentView === 'upload' ? 'active' : ''}>
            Upload
          </button>
        </nav>
      </header>

      <main className="App-main">
        {currentView === 'dashboard' && <Dashboard />}
        {currentView === 'upload' && <Upload onUpload={handleUpload} />}
        {currentView === 'history' && <ProcessingHistory onOpenDocument={openProcessing} />}
        {currentView === 'processing' && <ProcessingView docs={uploadedDocs} />}
      </main>

      <footer className="App-footer">
        <p>Powered by CrewAI • FastAPI • React • Tesseract OCR</p>
      </footer>
    </div>
  );
}

export default App;
