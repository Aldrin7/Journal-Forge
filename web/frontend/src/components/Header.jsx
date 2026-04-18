import React from 'react';

export default function Header() {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="logo">
          <span className="logo-icon">📄</span>
          <h1>PaperForge</h1>
        </div>
        <p className="tagline">Universal Agentic Research-to-Journal Converter</p>
        <div className="header-badges">
          <span className="badge">Offline</span>
          <span className="badge">3 GB RAM</span>
          <span className="badge">40+ Journals</span>
        </div>
      </div>
    </header>
  );
}
