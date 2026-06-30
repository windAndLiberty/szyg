<template>
  <canvas ref="canvas" class="tech-bg"></canvas>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvas = ref(null)
let raf = 0

onMounted(() => {
  const c = canvas.value
  const ctx = c.getContext('2d')
  let w, h

  const resize = () => {
    w = c.width = window.innerWidth
    h = c.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  // Particle system
  const PARTICLE_COUNT = 60
  const CONNECTION_DIST = 140
  const particles = []

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      r: Math.random() * 1.5 + 0.5,
      alpha: Math.random() * 0.4 + 0.2,
    })
  }

  // Grid config
  const GRID_SIZE = 60
  let time = 0

  const draw = () => {
    ctx.clearRect(0, 0, w, h)
    time += 0.003

    // 1. Draw subtle perspective grid
    ctx.save()
    ctx.strokeStyle = 'rgba(34, 211, 238, 0.04)'
    ctx.lineWidth = 0.5

    const offsetY = (time * 20) % GRID_SIZE

    // Horizontal lines with wave
    for (let y = -GRID_SIZE; y < h + GRID_SIZE; y += GRID_SIZE) {
      ctx.beginPath()
      for (let x = 0; x <= w; x += 4) {
        const wave = Math.sin(x * 0.005 + time * 2) * 8
        const yPos = y + offsetY + wave
        if (x === 0) ctx.moveTo(x, yPos)
        else ctx.lineTo(x, yPos)
      }
      ctx.stroke()
    }

    // Vertical lines
    for (let x = 0; x <= w; x += GRID_SIZE) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, h)
      ctx.stroke()
    }
    ctx.restore()

    // 2. Draw radial glow spots (very subtle)
    const glows = [
      { x: w * 0.15, y: h * 0.25, r: 300, c: '34, 211, 238' },
      { x: w * 0.85, y: h * 0.7, r: 350, c: '139, 92, 246' },
      { x: w * 0.5, y: h * 0.5, r: 400, c: '59, 130, 246' },
    ]

    for (const g of glows) {
      const grd = ctx.createRadialGradient(g.x, g.y, 0, g.x, g.y, g.r)
      grd.addColorStop(0, `rgba(${g.c}, 0.04)`)
      grd.addColorStop(0.5, `rgba(${g.c}, 0.015)`)
      grd.addColorStop(1, 'transparent')
      ctx.fillStyle = grd
      ctx.fillRect(0, 0, w, h)
    }

    // 3. Update and draw particles
    for (const p of particles) {
      p.x += p.vx
      p.y += p.vy

      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(148, 163, 184, ${p.alpha})`
      ctx.fill()
    }

    // 4. Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)

        if (dist < CONNECTION_DIST) {
          const alpha = (1 - dist / CONNECTION_DIST) * 0.08
          ctx.beginPath()
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(34, 211, 238, ${alpha})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }

    raf = requestAnimationFrame(draw)
  }

  draw()

  onBeforeUnmount(() => {
    cancelAnimationFrame(raf)
    window.removeEventListener('resize', resize)
  })
})
</script>

<style scoped>
.tech-bg {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}
</style>
