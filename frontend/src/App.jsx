import React, { useEffect, useMemo, useState } from 'react'
import Viewer from './components/Viewer.jsx'
import * as api from './lib/api.js'

const STAGES = ['problem', 'evidence', 'design', 'cad', 'print', 'done']
const STAGE_IDX = Object.fromEntries(STAGES.map((s, i) => [s, i]))

const excerpt = (t, n = 420) => {
  if (!t) return ''
  const s = String(t)
  return s.length > n ? s.slice(0, n) + '…' : s
}

function Status({ value }) {
  const label = { idle: 'pending', busy: 'working', ok: 'done', warn: 'review', bad: 'blocked' }[value] || value
  return <span className={`status ${value}`}>{label}</span>
}

export default function App() {
  const [projects, setProjects] = useState([])
  const [active, setActive] = useState(null)
  const [out, setOut] = useState({})
  const [runs, setRuns] = useState([])
  const [form, setForm] = useState({ title: '', problem: '' })
  const [busy, setBusy] = useState(false)
  const [busyStep, setBusyStep] = useState(null)
  const [stlPath, setStlPath] = useState(null)
  const [cadFiles, setCadFiles] = useState([])
  const [kbq, setKbq] = useState('')
  const [brief, setBrief] = useState('')
  const [provider, setProvider] = useState('…')

  const refresh = async () => {
    const p = await api.listProjects()
    setProjects(p)
    if (!active && p.length) { setActive(p[0]); loadCad(p[0].id); loadRuns(p[0].id) }
    else if (active) { const f = p.find(x => x.id === active.id); if (f) setActive(f) }
  }
  useEffect(() => {
    refresh().catch(e => setOut({ boot: { error: String(e) } }))
    fetch('/api/health').then(r => r.json()).then(h => setProvider(h.provider || '?')).catch(() => setProvider('?'))
  }, [])

  const loadRuns = async (pid) => setRuns(await api.listRuns(pid).catch(() => []))
  const loadCad = async (pid) => {
    try { const r = await api.listCad(pid); setCadFiles(r.files || []) } catch { setCadFiles([]) }
  }

  const runStep = async (stepId, fn, outKey) => {
    if (!active || busy) return
    setBusy(true); setBusyStep(stepId)
    try {
      const r = await fn()
      setOut(prev => ({ ...prev, [outKey]: r }))
      if (r && r.stl_file) setStlPath(r.stl_file)
      if (r && r.codegen && r.codegen.stl_file) setStlPath(r.codegen.stl_file)
      await refresh(); await loadRuns(active.id); await loadCad(active.id)
    } catch (e) {
      setOut(prev => ({ ...prev, [outKey]: { error: String(e?.response?.data?.detail || e?.message || e) } }))
    }
    setBusy(false); setBusyStep(null)
  }

  const fullRun = async () => {
    if (!active || busy) return
    setBusy(true); setBusyStep('full')
    setOut(prev => ({ ...prev, fullrun: { status: 'running' } }))
    try {
      const r = await api.fullRun({ project_id: active.id, brief, skip_research: false })
      if (r.codegen && r.codegen.stl_file) setStlPath(r.codegen.stl_file)
      setOut(prev => ({ ...prev, fullrun: r }))
      await refresh(); await loadRuns(active.id); await loadCad(active.id)
    } catch (e) {
      setOut(prev => ({ ...prev, fullrun: { error: String(e?.response?.data?.detail || e?.message || e) } }))
    }
    setBusy(false); setBusyStep(null)
  }

  const fr = out.fullrun && !out.fullrun.error ? out.fullrun : null
  const research = out.research || (fr && { papers: fr.research?.papers, synthesis: fr.research?.synthesis })
  const spec = out.spec || (fr && fr.spec ? { raw: fr.spec } : null)
  const safety = out.safety || (fr && fr.safety)
  const codegen = out.codegen || (fr && fr.codegen ? { ...fr.codegen, stl_note: undefined } : null)
  const packet = out.packet || (fr && fr.packet)

  const stageIdx = STAGE_IDX[active?.stage] ?? 0
  const stepState = (n) => {
    const order = { research: 1, spec: 2, safety: 2, cad: 3, print: 4 }
    if (busyStep === 'full') return stageIdx >= order[n] ? 'ok' : (n === 'research' ? 'busy' : 'idle')
    return 'idle'
  }

  const stepper = useMemo(() => {
    const items = [
      { id: 'problem', label: 'Need' },
      { id: 'evidence', label: 'Evidence' },
      { id: 'design', label: 'Design' },
      { id: 'cad', label: 'CAD / STL' },
      { id: 'print', label: 'Print' },
    ]
    const cur = active?.stage === 'problem' ? 0 : active?.stage === 'evidence' ? 1 : active?.stage === 'design' ? 2 : (active?.stage === 'cad' ? 3 : 4)
    return (
      <div className="stepper">
        {items.map((s, i) => (
          <div key={s.id} data-n={i + 1} className={`step ${i < cur || active?.stage === 'done' ? 'done' : i === cur ? 'current' : ''}`}>{s.label}</div>
        ))}
      </div>
    )
  }, [active?.stage])

  const safetyBlocked = safety && (safety.verdict || '').startsWith('BLOCKED')

  return (
    <>
      <header className="hdr">
        <div className="mark">B</div>
        <div>
          <h1>BiomedEng Harness</h1>
          <p className="sub">Need → evidence → design → CAD → print · research prototypes only</p>
        </div>
        <div className="spacer" />
        <span className="badge"><span className={`dot ${busy ? 'busy' : ''}`} />{busy ? (busyStep === 'full' ? 'full run working' : `${busyStep} working`) : 'idle'} · <span className="kbd">llm:{provider}</span></span>
        <button className="btn run" disabled={!active || busy} onClick={fullRun}>Full run</button>
      </header>

      <div className="wrap">
        <div className="board">
          {/* ------- projects ------- */}
          <aside className="card">
            <h3>Projects</h3>
            {projects.map(p => (
              <div key={p.id} className={`proj ${active?.id === p.id ? 'active' : ''}`}
                onClick={() => { setActive(p); setOut({}); setStlPath(null); loadRuns(p.id); loadCad(p.id) }}>
                <div className="t">{p.title}</div>
                <div className="m">{p.id}</div>
                <span className={`pill ${p.stage}`}>{p.stage}</span>
              </div>
            ))}
            {projects.length === 0 && <div className="empty">No projects yet — create the first need below.</div>}
            <label className="lbl">New need</label>
            <input className="input" placeholder="e.g. One-handed pill opener" value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })} />
            <div className="mt"><input className="input" placeholder="Who struggles + what hurts?" value={form.problem}
              onChange={e => setForm({ ...form, problem: e.target.value })} /></div>
            <div className="row mt">
              <button className="btn primary" disabled={busy || !form.title}
                onClick={async () => {
                  setBusy(true)
                  try {
                    const p = await api.createProject({ title: form.title, problem: form.problem })
                    setForm({ title: '', problem: '' })
                    await refresh(); setActive(p); setOut({}); loadRuns(p.id); loadCad(p.id)
                  } finally { setBusy(false) }
                }}>Create</button>
            </div>
            <label className="lbl">Stage gate (human approval)</label>
            <select className="input" value={active?.stage || 'problem'}
              onChange={async e => {
                if (!active) return
                const p = await api.updateProject(active.id, { stage: e.target.value })
                setActive(p); refresh()
              }}>
              {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <div className="mt" style={{ fontSize: 11, color: 'var(--faint)' }}>
              Gates: approve the need before design, the spec before CAD, the STL before printing.
            </div>
          </aside>

          {/* ------- workflow ------- */}
          <main className="card">
            {!active ? <div className="empty">Select a project to start the workflow.</div> : <>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <div><h2>{active.title}</h2><div style={{ color: 'var(--muted)', fontSize: 12.5 }}>{active.problem || 'No problem statement yet.'}</div></div>
                <span className={`pill ${active.stage}`}>{active.stage}</span>
              </div>
              <div className="mt">{stepper}</div>
              {busyStep === 'full' && <div className="progress"><div /></div>}

              <div className="steps">
                <section className={`stepcard ${research && !research.error ? 'done' : ''}`}>
                  <div className="head">
                    <div className="num">1</div>
                    <div className="grow"><div className="title">Evidence</div><div className="desc">PubMed + Semantic Scholar + local knowledge base</div></div>
                    <Status value={busyStep === 'research' || busyStep === 'full' ? 'busy' : research ? 'ok' : 'idle'} />
                    <button className="btn small" disabled={busy} onClick={() => runStep('research', () => api.research({ project_id: active.id, query: `${active.title} ${active.problem}` }), 'research')}>Run</button>
                  </div>
                  {research && <div className="body">
                    {research.error ? <span style={{ color: 'var(--red)' }}>{research.error}</span> : <>
                      <b>{research.papers ?? research.papers?.length ?? ''}</b>{typeof research.papers === 'number' ? ' papers found.' : ''}
                      {research.synthesis && <div className="excerpt">{excerpt(research.synthesis)}</div>}
                    </>}
                  </div>}
                </section>

                <section className={`stepcard ${spec && !spec.error ? 'done' : ''}`}>
                  <div className="head">
                    <div className="num">2</div>
                    <div className="grow"><div className="title">Design spec</div><div className="desc">3 concepts → chosen spec, dims, materials, failure modes</div></div>
                    <Status value={busyStep === 'spec' ? 'busy' : spec ? 'ok' : 'idle'} />
                    <button className="btn small" disabled={busy} onClick={() => runStep('spec', () => api.makeSpec({ project_id: active.id }), 'spec')}>Run</button>
                  </div>
                  {spec && <div className="body">
                    {spec.error ? <span style={{ color: 'var(--red)' }}>{spec.error}</span> :
                      <div className="excerpt">{excerpt(spec.raw || spec.concepts_text || JSON.stringify(spec))}</div>}
                  </div>}
                </section>

                <section className={`stepcard ${safety && !safety.error ? 'done' : ''}`}>
                  <div className="head">
                    <div className="num">3</div>
                    <div className="grow"><div className="title">Safety review</div><div className="desc">Risk flags + biocompat gate before any CAD</div></div>
                    <Status value={busyStep === 'safety' ? 'busy' : safetyBlocked ? 'bad' : safety ? 'ok' : 'idle'} />
                    <button className="btn small" disabled={busy} onClick={() => runStep('safety', () => api.safetyCheck({ project_id: active.id, title: active.title, problem: active.problem, spec: active.spec_json }), 'safety')}>Run</button>
                  </div>
                  {safety && !safety.error && <div className="body">
                    <span className={`verdict ${safetyBlocked ? 'block' : 'pass'}`}>{safety.verdict}</span>
                    {safety.flags?.length > 0 && <span className="mono" style={{ marginLeft: 8 }}>flags: {safety.flags.join(', ')}</span>}
                    {safety.review && <div className="excerpt">{excerpt(safety.review)}</div>}
                  </div>}
                  {safety?.error && <div className="body"><span style={{ color: 'var(--red)' }}>{safety.error}</span></div>}
                </section>

                <section className={`stepcard ${stlPath || codegen?.stl_file ? 'done' : ''}`}>
                  <div className="head">
                    <div className="num">4</div>
                    <div className="grow"><div className="title">CAD → STL</div><div className="desc">LLM CadQuery codegen with 3× auto-fix, min wall 2mm</div></div>
                    <Status value={busyStep === 'codegen' ? 'busy' : stlPath ? 'ok' : 'idle'} />
                    <button className="btn small" disabled={busy} onClick={() => runStep('codegen', () => api.genCad({ project_id: active.id }), 'cad')}>Template</button>
                    <button className="btn small primary btn" disabled={busy} onClick={() => runStep('codegen', () => api.codegenCad({ project_id: active.id, brief }), 'codegen')}>Generate</button>
                  </div>
                  <div className="body">
                    <input className="input" placeholder="Optional brief override — else uses project spec" value={brief} onChange={e => setBrief(e.target.value)} />
                    {(codegen?.attempts || fr?.codegen?.attempts) && (
                      <div className="mt" style={{ fontSize: 12 }}>
                        {(codegen?.attempts || fr.codegen.attempts).map(a => (
                          <div key={a.try}>try {a.try}: {a.ok ? <b style={{ color: 'var(--green)' }}>STL built</b> : <span style={{ color: 'var(--amber)' }}>{excerpt(a.note || a.error, 140)}</span>}</div>
                        ))}
                      </div>
                    )}
                    {codegen?.error && <span style={{ color: 'var(--red)' }}>{codegen.error}</span>}
                  </div>
                </section>

                <section className={`stepcard ${packet && !packet.error ? 'done' : ''}`}>
                  <div className="head">
                    <div className="num">5</div>
                    <div className="grow"><div className="title">Print packet</div><div className="desc">Validate mesh → slicer profile → preflight checklist</div></div>
                    <Status value={busyStep === 'validate' || busyStep === 'packet' ? 'busy' : packet ? 'ok' : 'idle'} />
                    <button className="btn small" disabled={busy || !stlPath} onClick={() => runStep('validate', () => api.validateStl({ stl_file: stlPath }), 'validate')}>Validate</button>
                    <button className="btn small" disabled={busy} onClick={() => runStep('packet', () => api.printPacket({ project_id: active.id, stl_file: stlPath }), 'packet')}>Packet</button>
                    <button className="btn small ghost btn" disabled={busy || !stlPath} onClick={() => runStep('slice', () => api.sliceModel({ stl_file: stlPath }), 'slice')}>Slice</button>
                  </div>
                  {(out.validate || fr?.validate) && <div className="body">
                    {(() => { const v = out.validate || fr.validate; return v.error ? v.error : v.watertight === undefined ? excerpt(JSON.stringify(v)) :
                      <>watertight: <b style={{ color: v.watertight ? 'var(--green)' : 'var(--amber)' }}>{String(v.watertight)}</b>{v.volume_mm3 != null && <> · vol {v.volume_mm3.toFixed(0)} mm³</>}{v.faces != null && <> · {v.faces} faces</>}</> })()}
                  </div>}
                  {packet && !packet.error && <div className="body">
                    {(packet.preflight || []).map(p => <div key={p}>· {p}</div>)}
                    {packet.disclaimer && <div className="mono mt">{packet.disclaimer}</div>}
                  </div>}
                </section>
              </div>

              <div className="viewer-card">
                <Viewer stlUrl={stlPath ? api.cadDownloadUrl(stlPath) : null} note={codegen?.note} />
                {stlPath && <div className="dl"><a href={api.cadDownloadUrl(stlPath)}>Download STL</a> <span className="mono">{stlPath}</span></div>}
                {cadFiles.length > 0 && <div className="filechips">{cadFiles.slice(0, 6).map(f => (
                  <button key={f.path} className="chip" onClick={() => f.name.endsWith('.stl') && setStlPath(f.path)}>{f.name}</button>
                ))}</div>}
              </div>

              <div className="mt">
                <div className="row">
                  <input className="input" placeholder="Ask local knowledge — FDA class, FDM rules, biocompat…" value={kbq} onChange={e => setKbq(e.target.value)} />
                  <button className="btn" disabled={busy || !kbq} onClick={() => runStep('kb', () => api.kbQuery({ query: kbq }), 'kb')}>Ask</button>
                </div>
                {out.kb && !out.kb.error && <div className="body mt">{out.kb.hits?.map((h, i) => (
                  <div key={i} className="excerpt"><b>[{h.source}]</b> {excerpt(h.text, 300)}</div>
                ))}{out.kb.hits?.length === 0 && <span className="empty">No local hits — ingest notes via API first.</span>}</div>}
              </div>
            </>}
          </main>

          {/* ------- traces ------- */}
          <aside className="card rail">
            <h3>Agent trace</h3>
            <div className="row mt"><button className="btn small ghost btn" onClick={() => active && loadRuns(active.id)}>Refresh</button>
              <span style={{ fontSize: 11, color: 'var(--faint)' }}>{runs.length} events</span></div>
            <div className="mt">
              {runs.length === 0 && <div className="empty">Every agent step lands here.</div>}
              {runs.map(r => (
                <div key={r.id} className={`trace ${r.status !== 'ok' ? 'warn' : ''}`}>
                  <span className="a">{r.agent}/{r.action}</span><span className={`s ${r.status}`}>{r.status}</span>
                  <div className="o">{excerpt(r.output_summary, 200)}</div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </>
  )
}
