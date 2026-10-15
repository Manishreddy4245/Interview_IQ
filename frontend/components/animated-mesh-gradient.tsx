'use client'

import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

type Blob = { x: number; y: number; rx: number; ry: number; p: number; p2: number; color: string }

const seed = 174074637
const blobs: Blob[] = [
  { x: 16, y: 18, rx: 42, ry: 34, p: 1.14, p2: 2.42, color: '#EEF2FF' },
  { x: 78, y: 20, rx: 38, ry: 32, p: 2.91, p2: 1.27, color: '#EAF3FF' },
  { x: 48, y: 68, rx: 44, ry: 36, p: 4.08, p2: 3.31, color: '#E0E7FF' },
  { x: 86, y: 78, rx: 32, ry: 30, p: 5.44, p2: 4.63, color: '#D6F0E4' },
]

export function AnimatedMeshGradient({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = ref.current
    if (!element || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let frame = 0
    const start = performance.now()
    const animate = (now: number) => {
      const ph = (now - start) / 1000
      const amt = 0.4
      blobs.forEach((blob, index) => {
        const x = (Math.sin(ph * 0.55 + blob.p) - Math.sin(blob.p)) * 14 * amt
        const y = (Math.sin(ph * 0.43 + blob.p2) - Math.sin(blob.p2)) * 14 * amt
        element.style.setProperty(`--blob-${index}-x`, `${blob.x + x}%`)
        element.style.setProperty(`--blob-${index}-y`, `${blob.y + y}%`)
      })
      frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [])

  return <div ref={ref} aria-hidden="true" data-seed={seed} className={cn('animated-mesh-gradient', className)} />
}

export default AnimatedMeshGradient
