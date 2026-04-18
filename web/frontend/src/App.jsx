import React, { useState } from 'react';
import Header from './components/Header';
import UploadMode from './pages/UploadMode';
import TemplateMode from './pages/TemplateMode';
import JournalSelector from './components/JournalSelector';
import ResultPanel from './components/ResultPanel';

const API_BASE = '/api/v1';

export default function App() {
  const [mode, setMode] = useState('upload'); // 'upload' | 'template'
  const [journal, setJournal] = useState('ieee');
  const [format, setFormat] = useState('docx');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleConvert = async (formData) => {
    setLoading(true);
    setResult(null);

    try {
      let response;
      if (mode === 'upload') {
        response = await fetch(`${API_BASE}/convert`, {
          method: 'POST',
          body: formData,
        });
      } else {
        formData.journal = journal;
        formData.format = format;
        response = await fetch(`${API_BASE}/template`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setResult({
        status: 'failed',
        message: `Network error: ${err.message}`,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <Header />

      <main className="main">
        {/* Mode Selector */}
        <div className="mode-selector">
          <button
            className={`mode-btn ${mode === 'upload' ? 'active' : ''}`}
            onClick={() => setMode('upload')}
          >
            📁 Upload Document
          </button>
          <button
            className={`mode-btn ${mode === 'template' ? 'active' : ''}`}
            onClick={() => setMode('template')}
          >
            📝 Universal Template
          </button>
        </div>

        {/* Journal & Format Selection */}
        <JournalSelector
          journal={journal}
          setJournal={setJournal}
          format={format}
          setFormat={setFormat}
        />

        {/* Content Area */}
        <div className="content-area">
          {mode === 'upload' ? (
            <UploadMode
              journal={journal}
              format={format}
              onConvert={handleConvert}
              loading={loading}
            />
          ) : (
            <TemplateMode
              journal={journal}
              format={format}
              onConvert={handleConvert}
              loading={loading}
            />
          )}
        </div>

        {/* Result */}
        {result && <ResultPanel result={result} />}
      </main>

      <footer className="footer">
        <p>PaperForge v1.0 — Universal Agentic Research-to-Journal Converter</p>
        <p>Runs entirely offline · 3 GB RAM · 45-min sessions</p>
      </footer>
    </div>
  );
}
