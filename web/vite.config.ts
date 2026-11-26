import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import svgr from 'vite-plugin-svgr'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss(), svgr()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text'],
      include: ['src/lib/**/*.ts', 'src/data/**/*.ts'],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 70,
        statements: 80,
      },
    },
  },
})
