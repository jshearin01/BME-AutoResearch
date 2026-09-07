import React from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

// v0 placeholder viewer: shows build plate + note. Phase 2 loads real STL via STLLoader.
export default function Viewer({ note }) {
  return (
    <div style={{ height: 320, background: '#0b0f14', borderRadius: 8, position: 'relative' }}>
      <Canvas camera={{ position: [80, 80, 80] }}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[50, 80, 30]} intensity={1.2} />
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -13, 0]}>
          <planeGeometry args={[160, 160]} />
          <meshStandardMaterial color="#1c2733" />
        </mesh>
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[80, 25, 45]} />
          <meshStandardMaterial color="#4cc3ff" wireframe />
        </mesh>
        <OrbitControls />
      </Canvas>
      <div style={{ position: 'absolute', bottom: 8, left: 10, color: '#9fb3c8', fontSize: 12 }}>
        {note || 'Parametric preview placeholder — export STL to view exact mesh (Phase 2: STLLoader).'}
      </div>
    </div>
  )
}
