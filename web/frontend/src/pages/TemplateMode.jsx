import React, { useState } from 'react';

export default function TemplateMode({ journal, format, onConvert, loading }) {
  const [title, setTitle] = useState('');
  const [authors, setAuthors] = useState('');
  const [abstract, setAbstract] = useState('');
  const [keywords, setKeywords] = useState('');
  const [sections, setSections] = useState([
    { level: 1, title: 'Introduction', content: '' },
    { level: 1, title: 'Related Work', content: '' },
    { level: 1, title: 'Methodology', content: '' },
    { level: 1, title: 'Results', content: '' },
    { level: 1, title: 'Discussion', content: '' },
    { level: 1, title: 'Conclusion', content: '' },
  ]);
  const [equations, setEquations] = useState(['']);

  const addSection = () => {
    setSections([...sections, { level: 1, title: '', content: '' }]);
  };

  const removeSection = (idx) => {
    setSections(sections.filter((_, i) => i !== idx));
  };

  const updateSection = (idx, field, value) => {
    const updated = [...sections];
    updated[idx] = { ...updated[idx], [field]: value };
    setSections(updated);
  };

  const addEquation = () => {
    setEquations([...equations, '']);
  };

  const removeEquation = (idx) => {
    setEquations(equations.filter((_, i) => i !== idx));
  };

  const updateEquation = (idx, value) => {
    const updated = [...equations];
    updated[idx] = value;
    setEquations(updated);
  };

  const handleSubmit = () => {
    const data = {
      title,
      authors: authors.split(',').map(a => a.trim()).filter(Boolean),
      abstract,
      keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
      sections: sections.filter(s => s.title || s.content),
      equations: equations.filter(e => e.trim()),
    };
    onConvert(data);
  };

  return (
    <div className="template-mode">
      <h2>📝 Universal Template Mode</h2>
      <p className="description">
        Build your paper section by section using the universal template.
        Content will be converted to your selected journal format with proper
        citations, equations, and styling.
      </p>

      {/* Title */}
      <div className="form-group">
        <label>Paper Title</label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Enter your paper title..."
          className="form-input"
        />
      </div>

      {/* Authors */}
      <div className="form-group">
        <label>Authors</label>
        <input
          type="text"
          value={authors}
          onChange={(e) => setAuthors(e.target.value)}
          placeholder="Author 1, Author 2, Author 3..."
          className="form-input"
        />
      </div>

      {/* Abstract */}
      <div className="form-group">
        <label>Abstract</label>
        <textarea
          value={abstract}
          onChange={(e) => setAbstract(e.target.value)}
          placeholder="Enter your abstract..."
          className="form-textarea"
          rows={4}
        />
      </div>

      {/* Keywords */}
      <div className="form-group">
        <label>Keywords</label>
        <input
          type="text"
          value={keywords}
          onChange={(e) => setKeywords(e.target.value)}
          placeholder="keyword1, keyword2, keyword3..."
          className="form-input"
        />
      </div>

      {/* Sections */}
      <div className="form-group">
        <label>Sections</label>
        {sections.map((section, idx) => (
          <div key={idx} className="section-block">
            <div className="section-header">
              <select
                value={section.level}
                onChange={(e) => updateSection(idx, 'level', parseInt(e.target.value))}
                className="level-select"
              >
                <option value={1}>H1 — Section</option>
                <option value={2}>H2 — Subsection</option>
                <option value={3}>H3 — Sub-subsection</option>
              </select>
              <input
                type="text"
                value={section.title}
                onChange={(e) => updateSection(idx, 'title', e.target.value)}
                placeholder="Section title..."
                className="section-title-input"
              />
              <button
                className="remove-btn"
                onClick={() => removeSection(idx)}
                title="Remove section"
              >
                ✕
              </button>
            </div>
            <textarea
              value={section.content}
              onChange={(e) => updateSection(idx, 'content', e.target.value)}
              placeholder="Section content... (use $equation$ for inline math, $$equation$$ for display math)"
              className="section-content"
              rows={3}
            />
          </div>
        ))}
        <button className="add-btn" onClick={addSection}>
          + Add Section
        </button>
      </div>

      {/* Equations */}
      <div className="form-group">
        <label>Display Equations (LaTeX)</label>
        {equations.map((eq, idx) => (
          <div key={idx} className="equation-block">
            <span className="eq-label">E{idx + 1}:</span>
            <input
              type="text"
              value={eq}
              onChange={(e) => updateEquation(idx, e.target.value)}
              placeholder="E = mc^2"
              className="equation-input"
            />
            <button
              className="remove-btn"
              onClick={() => removeEquation(idx)}
            >
              ✕
            </button>
          </div>
        ))}
        <button className="add-btn" onClick={addEquation}>
          + Add Equation
        </button>
      </div>

      {/* Hint */}
      <div className="folder-hint">
        <p>💡 <strong>Tip:</strong> Use <code>$...$</code> for inline math and <code>$$...$$</code> for display equations
           in section content. Citations can be added as <code>[@key]</code>.</p>
      </div>

      {/* Convert button */}
      <button
        className="convert-btn"
        onClick={handleSubmit}
        disabled={!title || loading}
      >
        {loading ? (
          <>
            <span className="spinner"></span> Converting...
          </>
        ) : (
          <>
            🚀 Generate {journal.toUpperCase()} ({format.toUpperCase()})
          </>
        )}
      </button>
    </div>
  );
}
