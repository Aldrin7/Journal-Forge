import React, { useState, useEffect } from 'react';

const JOURNALS = [
  { id: 'ieee', name: 'IEEE Transactions', category: 'IEEE' },
  { id: 'ieee-access', name: 'IEEE Access', category: 'IEEE' },
  { id: 'ieee-conference', name: 'IEEE Conference', category: 'IEEE' },
  { id: 'ieee-tpami', name: 'IEEE TPAMI', category: 'IEEE' },
  { id: 'ieee-tkde', name: 'IEEE TKDE', category: 'IEEE' },
  { id: 'ieee-tsp', name: 'IEEE TSP', category: 'IEEE' },
  { id: 'ieee-tse', name: 'IEEE TSE', category: 'IEEE' },
  { id: 'ieee-spl', name: 'IEEE Signal Processing Letters', category: 'IEEE' },
  { id: 'springer', name: 'Springer Nature', category: 'Springer' },
  { id: 'springer-lncs', name: 'Springer LNCS', category: 'Springer' },
  { id: 'springer-lnai', name: 'Springer LNAI', category: 'Springer' },
  { id: 'nature', name: 'Nature', category: 'Nature' },
  { id: 'elsevier', name: 'Elsevier', category: 'Elsevier' },
  { id: 'elsevier-cviu', name: 'Elsevier CVIU', category: 'Elsevier' },
  { id: 'elsevier-nuclear', name: 'Elsevier Nuclear', category: 'Elsevier' },
  { id: 'wiley', name: 'Wiley', category: 'Wiley' },
  { id: 'wiley-njd', name: 'Wiley NJD', category: 'Wiley' },
  { id: 'wiley-advanced', name: 'Wiley Advanced', category: 'Wiley' },
  { id: 'mdpi', name: 'MDPI', category: 'MDPI' },
  { id: 'mdpi-sensors', name: 'MDPI Sensors', category: 'MDPI' },
  { id: 'mdpi-molecules', name: 'MDPI Molecules', category: 'MDPI' },
  { id: 'acm', name: 'ACM', category: 'ACM' },
  { id: 'plos', name: 'PLOS ONE', category: 'Open Access' },
  { id: 'frontiers', name: 'Frontiers', category: 'Open Access' },
  { id: 'bmj', name: 'BMJ', category: 'Medical' },
  { id: 'acs', name: 'ACS (American Chemical Society)', category: 'Chemistry' },
  { id: 'taylor-francis', name: 'Taylor & Francis', category: 'Taylor & Francis' },
  { id: 'oxford', name: 'Oxford University Press', category: 'Oxford' },
];

const FORMATS = [
  { id: 'docx', name: 'Word (.docx)', icon: '📄' },
  { id: 'pdf', name: 'PDF', icon: '📕' },
  { id: 'latex', name: 'LaTeX (.tex)', icon: '📐' },
  { id: 'jats', name: 'JATS XML', icon: '📰' },
  { id: 'html', name: 'HTML', icon: '🌐' },
  { id: 'epub', name: 'ePub', icon: '📚' },
];

export default function JournalSelector({ journal, setJournal, format, setFormat }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  const categories = ['All', ...new Set(JOURNALS.map(j => j.category))];

  const filteredJournals = JOURNALS.filter(j => {
    const matchSearch = j.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                        j.id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchCategory = selectedCategory === 'All' || j.category === selectedCategory;
    return matchSearch && matchCategory;
  });

  return (
    <div className="journal-selector">
      <div className="selector-section">
        <h3>📋 Target Journal</h3>
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search journals..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
        <div className="category-tabs">
          {categories.map(cat => (
            <button
              key={cat}
              className={`cat-tab ${selectedCategory === cat ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className="journal-grid">
          {filteredJournals.map(j => (
            <button
              key={j.id}
              className={`journal-card ${journal === j.id ? 'selected' : ''}`}
              onClick={() => setJournal(j.id)}
            >
              <span className="journal-name">{j.name}</span>
              <span className="journal-id">{j.id}</span>
            </button>
          ))}
        </div>
        <p className="selected-info">Selected: <strong>{journal}</strong></p>
      </div>

      <div className="selector-section">
        <h3>📦 Output Format</h3>
        <div className="format-grid">
          {FORMATS.map(f => (
            <button
              key={f.id}
              className={`format-card ${format === f.id ? 'selected' : ''}`}
              onClick={() => setFormat(f.id)}
            >
              <span className="format-icon">{f.icon}</span>
              <span className="format-name">{f.name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
