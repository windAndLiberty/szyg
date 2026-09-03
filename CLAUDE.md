# szyg — AI Marketing Platform

## Project Overview
szyg (玉灵) is an AI-powered marketing automation platform. It uses RPA (Robotic Process Automation) to manage social media accounts and automate content publishing, traffic interception, and sentiment monitoring across Chinese platforms (抖音, 小红书, 快手, B站, 微信, 微博).

## Tech Stack
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS
- Icons: lucide-react
- Animations: framer-motion
- Backend: Python (FastAPI-style), RPA via CDP Playwright + anti_detect

## Design System
See `szyg-frontend/DESIGN_SYSTEM.md` for full details. Quick reference:
- Background: `#0B0F1A` (dark theme)
- Card gradient: `linear-gradient(180deg, rgba(26,34,53,0.8) 0%, rgba(17,24,39,0.95) 100%)`
- Accent/primary: `#6366F1`
- Success: `#10B981`, Error: `#EF4444`, Warning: `#F59E0B`
- Border: `#1E293B`, Text primary: `#F1F5F9`, Text secondary: `#94A3B8`
- Card border-radius: 12px, Input border-radius: 10px

## Component Library
Reusable UI components in `szyg-frontend/src/components/ui/`:
- `Button`, `Card`, `Input`, `Badge`, `Empty`, `Avatar`, `Switch`, `Label`
- API client in `szyg-frontend/src/lib/api.ts` (JWT auth + auto-retry on 401)

## Design Principles
- Target users: Traditional SME clerks and bosses (non-technical)
- ≤ 3 core operations per page
- Chinese labels, no technical jargon
- One-click execution whenever possible
- Mobile responsive (single column mobile, multi-column desktop)
- Empty states MUST show: icon + "暂无数据" + guide action button
- Error states: red toast notification with retry button
- Loading states: skeleton screens or spinners in `#6366F1`

## Conventions
- All new pages replace existing Placeholder components (routes already defined in App.tsx)
- Use `@/` path alias for imports from `src/`
- Each page component exported as default
- Platform-specific RPA adapters in `server/szyg/platforms/`
- Backend engines: `publisher.py`, `intercept_engine.py`, `scheduler_engine.py`
