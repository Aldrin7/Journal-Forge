import React from 'react';

export default function ResultPanel({ result }) {
  const isSuccess = result.status === 'completed';

  return (
    <div className={`result-panel ${isSuccess ? 'success' : 'error'}`}>
      <div className="result-header">
        <span className="result-icon">{isSuccess ? '✅' : '❌'}</span>
        <h3>{isSuccess ? 'Conversion Complete' : 'Conversion Failed'}</h3>
      </div>

      <p className="result-message">{result.message}</p>

      {result.run_id && (
        <p className="result-run-id">Run ID: <code>{result.run_id}</code></p>
      )}

      {/* Output files */}
      {result.outputs && Object.keys(result.outputs).length > 0 && (
        <div className="outputs-section">
          <h4>📥 Output Files</h4>
          {Object.entries(result.outputs).map(([fmt, info]) => (
            <div key={fmt} className="output-item">
              <span className="output-format">{fmt.toUpperCase()}</span>
              <span className="output-size">
                {info.size_bytes ? `${(info.size_bytes / 1024).toFixed(1)} KB` : ''}
              </span>
              {result.run_id && (
                <a
                  href={`/api/v1/download/${result.run_id}/paper.${fmt === 'latex' ? 'tex' : fmt}`}
                  className="download-link"
                  download
                >
                  ⬇️ Download
                </a>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Audit info */}
      {result.audit && (
        <div className="audit-section">
          <h4>🔍 Audit Results</h4>
          <div className={`audit-badge ${result.audit.passed ? 'pass' : 'fail'}`}>
            {result.audit.passed ? 'PASSED' : 'FAILED'} — Score: {result.audit.score?.toFixed(0) || 'N/A'}/100
          </div>
          {result.audit.total_errors > 0 && (
            <p className="audit-stat error">❌ {result.audit.total_errors} errors</p>
          )}
          {result.audit.total_warnings > 0 && (
            <p className="audit-stat warning">⚠️ {result.audit.total_warnings} warnings</p>
          )}
        </div>
      )}
    </div>
  );
}
