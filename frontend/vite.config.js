import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// 개발 중에는 /api 요청을 백엔드(8000)로 프록시합니다.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg', 'favicon.svg'],
      manifest: {
        name: '오네시스 (Onesis)',
        short_name: '오네시스',
        description: '클로드·챗지피티·제미나이가 토론해 최선의 답을 만드는 개인 AI 앱',
        theme_color: '#6d5efc',
        background_color: '#ffffff',
        display: 'standalone',
        lang: 'ko',
        start_url: '/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'maskable' }
        ]
      },
      workbox: {
        // 앱 껍데기(HTML/JS/CSS)를 캐시해 오프라인에서도 열람 가능
        navigateFallback: '/index.html',
        globPatterns: ['**/*.{js,css,html,svg,woff2}']
      }
    })
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000'
    }
  },
  build: { outDir: 'dist' }
})
