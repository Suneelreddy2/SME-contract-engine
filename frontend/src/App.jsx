import React, { useState } from 'react'
import axios from 'axios'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || window.location.origin

function App() {
  const [contractText, setContractText] = useState('')
  const [language, setLanguage] = useState('english')
  const [businessRole, setBusinessRole] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('input')
  const [uploadFile, setUploadFile] = useState(null)
  const [inputMode, setInputMode] = useState('paste') // 'paste' | 'file'

  const handleAnalyze = async () => {
    if (inputMode === 'paste' && !contractText.trim()) {
      setError('Please enter contract text or upload a file')
      return
    }
    if (inputMode === 'file' && !uploadFile) {
      setError('Please select a PDF, DOCX, or TXT file')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      if (inputMode === 'file' && uploadFile) {
        const form = new FormData()
        form.append('file', uploadFile)
        form.append('language', language)
        if (businessRole) form.append('business_role', businessRole)
        const response = await axios.post(`${API_URL}/analyze/file`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        setResult(response.data.result)
      } else {
        const response = await axios.post(`${API_URL}/analyze`, {
          contract_text: contractText,
          language: language,
          business_role: businessRole || null,
        })
        setResult(response.data.result)
      }
      setActiveTab('overview')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(Array.isArray(detail) ? detail.map(d => d.msg).join(' ') : (detail || err.message || 'Analysis failed'))
    } finally {
      setLoading(false)
    }
  }

  const handleExportPdf = async () => {
    if (!result) return
    try {
      const response = await axios.post(`${API_URL}/export/pdf`, { result: result }, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'contract_analysis_report.pdf'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'PDF export failed')
    }
  }

  const getRiskColor = (score) => {
    if (score <= 30) return '#10b981' // green
    if (score <= 60) return '#f59e0b' // amber
    return '#ef4444' // red
  }

  const getRiskLabel = (score) => {
    if (score <= 30) return 'Safe'
    if (score <= 60) return 'Needs Review'
    return 'High Risk'
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🇮🇳 India SME Contract Intelligence Engine</h1>
        <p className="subtitle">Analyze business contracts • Identify risks • Get SME-friendly suggestions</p>
        <p className="disclaimer">Not legal advice. For informational purposes only.</p>
      </header>

      {!result ? (
        <div className="input-section">
          <div className="card">
            <h2>Enter Contract</h2>
            <div className="form-row input-mode">
              <label><input type="radio" checked={inputMode === 'paste'} onChange={() => { setInputMode('paste'); setUploadFile(null); }} /> Paste text</label>
              <label><input type="radio" checked={inputMode === 'file'} onChange={() => { setInputMode('file'); setContractText(''); }} /> Upload file (PDF, DOCX, TXT)</label>
            </div>
            {inputMode === 'paste' && (
              <div className="form-group">
                <label>Contract Text *</label>
                <textarea
                  value={contractText}
                  onChange={(e) => setContractText(e.target.value)}
                  placeholder="Paste your contract text here..."
                  rows={15}
                  className="textarea"
                />
              </div>
            )}
            {inputMode === 'file' && (
              <div className="form-group">
                <label>File *</label>
                <input
                  type="file"
                  accept=".pdf,.docx,.doc,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="file-input"
                />
                {uploadFile && <span className="file-name">{uploadFile.name}</span>}
              </div>
            )}

            <div className="form-row">
              <div className="form-group">
                <label>Language</label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="select"
                >
                  <option value="english">English</option>
                  <option value="hindi">Hindi</option>
                </select>
              </div>

              <div className="form-group">
                <label>Business Role (Optional)</label>
                <select
                  value={businessRole}
                  onChange={(e) => setBusinessRole(e.target.value)}
                  className="select"
                >
                  <option value="">Select...</option>
                  <option value="Startup">Startup</option>
                  <option value="SME">SME</option>
                  <option value="Vendor">Vendor</option>
                  <option value="Employer">Employer</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            {error && <div className="error">{error}</div>}

            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="analyze-btn"
            >
              {loading ? 'Analyzing...' : 'Analyze Contract'}
            </button>
          </div>
        </div>
      ) : (
        <div className="results-section">
          <div className="tabs">
            <button
              className={activeTab === 'overview' ? 'tab active' : 'tab'}
              onClick={() => setActiveTab('overview')}
            >
              Overview
            </button>
            <button
              className={activeTab === 'clauses' ? 'tab active' : 'tab'}
              onClick={() => setActiveTab('clauses')}
            >
              Clauses
            </button>
            <button
              className={activeTab === 'risks' ? 'tab active' : 'tab'}
              onClick={() => setActiveTab('risks')}
            >
              Risks
            </button>
            <button
              className={activeTab === 'suggestions' ? 'tab active' : 'tab'}
              onClick={() => setActiveTab('suggestions')}
            >
              Suggestions
            </button>
            <button
              className={activeTab === 'summary' ? 'tab active' : 'tab'}
              onClick={() => setActiveTab('summary')}
            >
              Summary
            </button>
            <button className="tab export-btn" onClick={handleExportPdf}>
              Export PDF
            </button>
            <button
              className="tab reset-btn"
              onClick={() => {
                setResult(null)
                setContractText('')
                setUploadFile(null)
                setActiveTab('input')
              }}
            >
              New Analysis
            </button>
          </div>

          {activeTab === 'overview' && (
            <div className="card">
              <h2>Contract Overview</h2>
              <div className="risk-score-card" style={{ borderColor: getRiskColor(result['7_contract_risk_score_summary'].composite_risk_score_0_to_100) }}>
                <div className="risk-score-number">
                  {result['7_contract_risk_score_summary'].composite_risk_score_0_to_100}
                </div>
                <div className="risk-score-label">
                  {getRiskLabel(result['7_contract_risk_score_summary'].composite_risk_score_0_to_100)}
                </div>
              </div>

              <div className="info-grid">
                <div className="info-item">
                  <strong>Contract Type:</strong>
                  <span>{result['1_contract_type_and_overview'].contract_type}</span>
                </div>
                <div className="info-item">
                  <strong>Explanation:</strong>
                  <span>{result['1_contract_type_and_overview'].explanation}</span>
                </div>
              </div>

              <h3>Key Entities</h3>
              <div className="entities">
                {result['3_entity_and_attribute_extraction'].parties.length > 0 && (
                  <div>
                    <strong>Parties:</strong>
                    <ul>
                      {result['3_entity_and_attribute_extraction'].parties.map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {result['3_entity_and_attribute_extraction'].jurisdiction_or_governing_law && (
                  <div>
                    <strong>Governing Law:</strong>
                    <span>{result['3_entity_and_attribute_extraction'].jurisdiction_or_governing_law}</span>
                  </div>
                )}
                {result['3_entity_and_attribute_extraction'].dates_and_duration?.duration_text && (
                  <div>
                    <strong>Duration:</strong>
                    <span>{result['3_entity_and_attribute_extraction'].dates_and_duration.duration_text}</span>
                  </div>
                )}
                {(result['3_entity_and_attribute_extraction'].termination_conditions?.length > 0) && (
                  <div>
                    <strong>Termination conditions:</strong>
                    <ul>
                      {result['3_entity_and_attribute_extraction'].termination_conditions.map((t, i) => (
                        <li key={i}>{t}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'clauses' && (
            <div className="card">
              <h2>Clause Analysis</h2>
              <div className="clauses-list">
                {result['4_clause_by_clause_explanation_table'].map((clause, idx) => (
                  <div key={idx} className="clause-item">
                    <div className="clause-header">
                      <span className="clause-number">Clause {clause.clause_number}</span>
                      <span className="clause-intent badge">{clause.intent}</span>
                    </div>
                    <h4>{clause.heading}</h4>
                    <p className="clause-impact">{clause.business_impact}</p>
                    {clause.template_matches?.length > 0 && (
                      <div className="template-matches">
                        <strong>Matches standard:</strong>
                        {clause.template_matches.map((m, i) => (
                          <span key={i} className="template-tag" title={m.matched_keywords?.join(', ')}>
                            {m.template_heading} ({Math.round((m.match_score || 0) * 100)}%)
                          </span>
                        ))}
                      </div>
                    )}
                    <details className="clause-details">
                      <summary>View Text</summary>
                      <pre className="clause-text">{clause.text_preview}</pre>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'risks' && (
            <div className="card">
              <h2>Risk Analysis</h2>
              {result['5_risk_analysis_and_flags'].ambiguity_flags?.length > 0 && (
                <div className="ambiguity-section">
                  <h3>Ambiguity flags</h3>
                  <ul className="ambiguity-list">
                    {result['5_risk_analysis_and_flags'].ambiguity_flags.map((a, idx) => (
                      <li key={idx}>
                        <strong>"{a.phrase}"</strong> — {a.reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="risks-list">
                {result['5_risk_analysis_and_flags'].clause_risk_table.map((risk, idx) => (
                  <div key={idx} className={`risk-item risk-${risk.risk_level.toLowerCase()}`}>
                    <div className="risk-header">
                      <span className="clause-number">Clause {risk.clause_number}</span>
                      <span className={`risk-badge risk-${risk.risk_level.toLowerCase()}`}>
                        {risk.risk_level}
                      </span>
                    </div>
                    <h4>{risk.heading}</h4>
                    {risk.flags?.length > 0 && (
                      <div className="risk-flags">
                        {risk.flags.map((flag, i) => (
                          <span key={i} className="flag-tag">{flag.replace(/_/g, ' ')}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'suggestions' && (
            <div className="card">
              <h2>Renegotiation Suggestions</h2>
              {result['6_renegotiation_suggestions'].length === 0 ? (
                <p className="no-suggestions">No high-risk clauses requiring renegotiation detected.</p>
              ) : (
                <div className="suggestions-list">
                  {result['6_renegotiation_suggestions'].map((suggestion, idx) => (
                    <div key={idx} className="suggestion-item">
                      <div className="suggestion-header">
                        <span className="clause-number">Clause {suggestion.clause_number}</span>
                        <span className={`risk-badge risk-${suggestion.risk_level.toLowerCase()}`}>
                          {suggestion.risk_level}
                        </span>
                      </div>
                      <h4>{suggestion.heading}</h4>
                      <p className="suggestion-text">{suggestion.suggested_change}</p>
                      <p className="suggestion-why">{suggestion.why_it_helps}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'summary' && (
            <div className="card">
              <h2>Executive Summary</h2>
              <div className="summary-section">
                <h3>Overview</h3>
                <p>{result['8_executive_business_summary'].overview}</p>
              </div>

              <div className="summary-section">
                <h3>Key Obligations</h3>
                <ul>
                  {(result['8_executive_business_summary'].key_obligations_to_note || []).map((ob, idx) => (
                    <li key={idx}>{ob}</li>
                  ))}
                </ul>
              </div>

              {result['8_executive_business_summary'].biggest_risks_in_simple_terms.length > 0 && (
                <div className="summary-section">
                  <h3>Biggest Risks</h3>
                  <ul>
                    {result['8_executive_business_summary'].biggest_risks_in_simple_terms.map((risk, idx) => (
                      <li key={idx} className="risk-item-summary">{risk}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="summary-section">
                <h3>What to Negotiate Before Signing</h3>
                <ul>
                  {(result['8_executive_business_summary'].what_to_negotiate_before_signing || []).map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="summary-section">
                <h3>Best Practices</h3>
                <ul>
                  {(result['9_sme_template_and_best_practices']?.recommendations || []).map((rec, idx) => (
                    <li key={idx}>{rec}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default App
