# Web Frontend

Next.js web application for Meeting Minutes.

## Setup

```bash
pnpm install
pnpm dev
```

App runs at: http://localhost:3000

## Key Differences from Desktop

- **No Tauri dependencies** - Pure web app
- **Web Audio API** - Browser microphone access
- **HTTP + WebSocket** - API communication
- **Axios** - HTTP client (replaces Tauri invoke)

## Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:5167
NEXT_PUBLIC_WS_URL=ws://localhost:5167
```

## Development

- `pnpm dev` - Start development server
- `pnpm build` - Build for production
- `pnpm start` - Run production build
- `pnpm lint` - Run ESLint
