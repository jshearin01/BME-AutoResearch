import React, { useEffect, useState } from 'react'
import Viewer from './components/Viewer.jsx'
import * as api from './lib/api.js'

const STAGES = ['problem', 'evidence', 'design', 'cad', 'print', 'done']

export default function App() {
  const [projects, setProjects] = useState([])
  const [active, setActive] = useState(null)
  const [out, setOut] = useState({})
  const [runs, setRuns] = useState([])
  const [form, setForm] = useState({ title: '', problem: '', users: '', constraints: '' })
  const [busy, setBusy] = useState(false)
  const [stlPath, setStlPath] = useState(null)
  const [cadFiles, setCadFiles] = useState([])
  const [kbq, setKbq] = useState('')
  const [brief, setBrief] = useState('')

  const refresh = async () => {
    const p = await api.listProjects()
    setProjects(p)
    if (!active && p.length) setActive(p[0])
    else if (active) { const f = p.find(x => x.id === active.id); if (f) setActive(f) }
  }
  useEffect(() => { refresh().catch(e => setOut({ error: String(e) })) }, [])

  const loadRuns = async (pid) => setRuns(await api.listRuns(pid).catch(() => []))
  const loadCad = async (pid) => {
    try { const r = await api.listCad(pid); setCadFiles(r.files || []) } catch {}
  }

  const step = async (fn, key) => {
    if (!active) return
    setBusy(true)
    try {
      const r = await fn()
      setOut({ [key]: r })
      if ((key === 'cad' || key === 'codegen') && r.stl_file) setStlPath(r.stl_file)
      await refresh(); await loadRuns(active.id); await loadCad(active.id)
    } catch (e) { setOut({ [key]: { error: String(e?.response?.data?.detail || e) } }) }
    setBusy(false)
  }

  return (
    <div style={{ fontFamily: 'system-ui', background: '#070b10', color: '#e6eef6', minHeight: '100vh', padding: 20 }}>
      <h2>BiomedEng Harness <span style={{ fontSize: 12, color: '#8fa3b8' }}>problem → evidence → CAD → print (research prototype only)</span></h2>
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr 360px', gap: 16 }}>
        <div style={{ background: '#0d141c', padding: 12, borderRadius: 8 }}>
          <h4>Projects</h4>
          {projects.map(p => (
            <div key={p.id} onClick={() => { setActive(p); loadRuns(p.id); loadCad(p.id) }}
              style={{ padding: 8, marginBottom: 6, borderRadius: 6, cursor: 'pointer', background: active?.id === p.id ? '#16324a' : '#111c26' }}>
              <b>{p.title}</b><div style={{ fontSize: 11, color: '#8fa3b8' }}>{p.id} · {p.stage}</div>
            </div>
          ))}
          <input placeholder="New project title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} style={{ width: '100%', marginTop: 8 }} />
          <button disabled={busy || !form.title} onClick={() => step(() => api.createProject({ title: form.title, problem: form.problem, users: form.users, constraints: form.constraints }), 'created')}>+ New</button>
          <div style={{ marginTop: 10, fontSize: 12 }}>
            <div>Stage gate:</div>
            <select value={active?.stage || 'problem'} onChange={e => step(() => api.updateProject(active.id, { stage: e.target.value }), 'stage')}>
              {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        <div style={{ background: '#0d141c', padding: 12, borderRadius: 8 }}>
          {!active ? <p>No project.</p> : <>
            <h3>{active.title}</h3>
            <p style={{ fontSize: 13, color: '#b8c7d6' }}>{active.problem}</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
              <button disabled={busy} onClick={() => step(() => api.research({ project_id: active.id, query: active.title + ' ' + active.problem }), 'research')}>1. Research</button>
              <button disabled={busy} onClick={() => step(() => api.makeSpec({ project_id: active.id }), 'spec')}>2. Design spec</button>
              <button disabled={busy} onClick={() => step(() => api.safetyCheck({ project_id: active.id, title: active.title, problem: active.problem, spec: active.spec_json }), 'safety')}>3. Safety check</button>
              <button disabled={busy} onClick={() => step(() => api.genCad({ project_id: active.id }), 'cad')}>4a. Template CAD</button>
              <button disabled={busy} onClick={() => step(() => api.codegenCad({ project_id: active.id, brief }), 'codegen')}>4b. LLM codegen ×3</button>
              <button disabled={busy || !stlPath} onClick={() => step(() => api.validateStl({ stl_file: stlPath }), 'validate')}>Validate STL</button>
              <button disabled={busy} onClick={() => step(() => api.printPacket({ project_id: active.id, stl_file: stlPath || out.cad?.stl_file || out.codegen?.stl_file }), 'packet')}>5. Print packet</button>
              <button disabled={busy || !stlPath} onClick={() => step(() => api.sliceModel({ stl_file: stlPath }), 'slice')}>Slice (Orca/Prusa if installed)</button>
            </div>
            <input placeholder="Optional codegen brief override (else uses spec)" value={brief} onChange={e => setBrief(e.target.value)} style={{ width: '100%', marginBottom: 8, background: '#090f15', color: '#e6eef6', border: '1px solid #1b2a3a', borderRadius: 6, padding: 6 }} />
            <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
              <input placeholder="Ask local knowledge (FDA/FDM/biocompat)…" value={kbq} onChange={e => setKbq(e.target.value)} style={{ flex: 1, background: '#090f15', color: '#e6eef6', border: '1px solid #1b2a3a', borderRadius: 6, padding: 6 }} />
              <button disabled={busy || !kbq} onClick={() => step(() => api.kbQuery({ query: kbq }), 'kb')}>Ask KB</button>
            </div>
            <Viewer stlUrl={stlPath ? api.cadDownloadUrl(stlPath) : null} note={out.cad?.stl_note} />
            {stlPath && <div style={{ fontSize: 12, margin: '6px 0' }}><a style={{ color: '#4cc3ff' }} href={api.cadDownloadUrl(stlPath)}>Download STL</a> <span style={{ color: '#8fa3b8' }}>{stlPath}</span></div>}
            {cadFiles.length > 0 && <div style={{ fontSize: 12, marginBottom: 6 }}>Recent files: {cadFiles.slice(0, 5).map(f => <button key={f.path} style={{ marginRight: 4, fontSize: 11 }} onClick={() => f.name.endsWith('.stl') && setStlPath(f.path)}>{f.name}</button>)}</div>}
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, background: '#090f15', padding: 10, borderRadius: 6, maxHeight: 380, overflow: 'auto' }}>
              {JSON.stringify(out, null, 2)}
            </pre>
          </>}
        </div>

        <div style={{ background: '#0d141c', padding: 12, borderRadius: 8 }}>
          <h4>Agent traces</h4>
          <button onClick={() => active && loadRuns(active.id)}>Refresh</button>
          {runs.map(r => (
            <div key={r.id} style={{ fontSize: 11, borderBottom: '1px solid #1b2a3a', padding: '6px 0' }}>
              <b>{r.agent}/{r.action}</b> <span style={{ color: r.status === 'ok' ? '#7dffa8' : '#ff8a8a' }}>{r.status}</span>
              <div style={{ color: '#8fa3b8' }}>{r.output_summary?.slice(0, 220)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
