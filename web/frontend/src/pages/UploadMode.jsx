import React, { useState, useRef } from 'react';

export default function UploadMode({ journal, format, onConvert, loading }) {
  const [file, setFile] = useState(null);
  const [bibFile, setBibFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);
  const bibRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleSubmit = () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('journal', journal);
    formData.append('output_format', format);
    if (bibFile) formData.append('bibliography', bibFile);

    onConvert(formData);
  };

  const acceptTypes = '.docx,.doc,.tex,.latex,.md,.markdown,.jats,.xml,.nxml';

  return (
    <div className="upload-mode">
      <h2>📁 Upload Your Manuscript</h2>
      <p className="description">
        Upload your paper in any supported format. PaperForge will parse, transform,
        audit, and convert it to your target journal's format.
      </p>

      {/* Main file drop zone */}
      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${file ? 'has-file' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          accept={acceptTypes}
          onChange={(e) => setFile(e.target.files[0])}
          style={{ display: 'none' }}
        />
        {file ? (
          <div className="file-info">
            <span className="file-icon">📄</span>
            <div>
              <p className="file-name">{file.name}</p>
              <p className="file-size">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <button
              className="remove-btn"
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
            >
              ✕
            </button>
          </div>
        ) : (
          <div className="drop-prompt">
            <span className="drop-icon">📂</span>
            <p>Drop your file here or <strong>click to browse</strong></p>
            <p className="supported">Supports: .docx, .tex, .md, .jats</p>
          </div>
        )}
      </div>

      {/* BibTeX file (optional) */}
      <div
        className="bib-zone"
        onClick={() => bibRef.current?.click()}
      >
        <input
          ref={bibRef}
          type="file"
          accept=".bib,.bibtex,.ris,.enl"
          onChange={(e) => setBibFile(e.target.files[0])}
          style={{ display: 'none' }}
        />
        {bibFile ? (
          <div className="file-info small">
            <span>📚 {bibFile.name}</span>
            <button
              className="remove-btn"
              onClick={(e) => { e.stopPropagation(); setBibFile(null); }}
            >
              ✕
            </button>
          </div>
        ) : (
          <p className="bib-prompt">📚 Optional: Add bibliography file (.bib)</p>
        )}
      </div>

      {/* Folder hint */}
      <div className="folder-hint">
        <p>💡 <strong>Figures & assets:</strong> Place them in the same folder as your manuscript.
           PaperForge will automatically resolve relative paths.</p>
      </div>

      {/* Convert button */}
      <button
        className="convert-btn"
        onClick={handleSubmit}
        disabled={!file || loading}
      >
        {loading ? (
          <>
            <span className="spinner"></span> Converting...
          </>
        ) : (
          <>
            🚀 Convert to {journal.toUpperCase()} ({format.toUpperCase()})
          </>
        )}
      </button>
    </div>
  );
}
