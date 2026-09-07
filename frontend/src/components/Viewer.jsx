import React, { useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import * as THREE from 'three'

function Mesh({ geometry }) {
  if (!geometry) return null
  geometry.computeVertexNormals()
  geometry.center()
  return (
    <mesh geometry={geometry}>
      <meshStandardMaterial color="#4cc3ff" roughness={0.4} metalness={0.1} />
    </mesh>
  )
}

// Props: stlUrl (backend /api/cad/download?path=...), note
export default function Viewer({ stlUrl, note, onFile }) {
  const [geom, setGeom] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (!stlUrl) return
    setErr('')
    new STLLoader().load(
      stlUrl,
      (g) => setGeom(g),
      undefined,
      (e) => setErr('STL load failed: ' + (e?.message || e))
    )
  }, [stlUrl])

  const uploadLocal = (f) => {
    if (!f) return
    const url = URL.createObjectURL(f)
    new STLLoader().load(url, (g) => { setGeom(g); setErr('') },
      undefined, (e) => setErr('Local STL parse failed'))
    onFile && onFile(f)
  }

  return (
    <div style={{ height: 340, background: '#0b0f14', borderRadius: 8, position: 'relative' }}>
      <Canvas camera={{ position: [90, 90, 90] }}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[50, 80, 30]} intensity={1.2} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -35, 0]}>
          <planeGeometry args={[220, 220]} />
          <meshStandardMaterial color="#1c2733" />
        </mesh>
        {geom ? <Mesh geometry={geom} /> : (
          <mesh position={[0, 0, 0]}>
            <boxGeometry args={[80, 25, 45]} />
            <meshStandardMaterial color="#4cc3ff" wireframe />
          </mesh>
        )}
        <OrbitControls />
      </Canvas>
      <div style={{ position: 'absolute', top: 8, right: 10, display: 'flex', gap: 6 }}>
        <label style={{ fontSize: 12, background: '#16324a', padding: '4px 8px', borderRadius: 6, cursor: 'pointer' }}>
          Open local STL
          <input type="file" accept=".stl" style={{ display: 'none' }} onChange={e => uploadLocal(e.target.files[0])} />
        </label>
      </div>
      <div style={{ position: 'absolute', bottom: 8, left: 10, color: '#9fb3c8', fontSize: 12, maxWidth: '90%' }}>
        {err ? <span style={{ color: '#ff8a8a' }}>{err}</span> : (note || (geom ? `Mesh loaded (${geom.attributes.position.count} verts) — drag to orbit.` : 'No STL yet — generate CAD or open a local STL.'))}
      </div>
    </div>
  )
}
