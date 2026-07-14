# Jarvis Mobile App

## Setup
```bash
npm install
npx expo start
```

## Structure
```
mobile/
├── App.tsx              # Entry point
├── src/
│   ├── screens/         # Screen components
│   │   ├── LoginScreen.tsx
│   │   ├── ChatScreen.tsx
│   │   ├── KnowledgeScreen.tsx
│   │   ├── TestingScreen.tsx
│   │   ├── FreelanceScreen.tsx
│   │   ├── PluginScreen.tsx
│   │   └── SettingsScreen.tsx
│   ├── components/      # Reusable components
│   ├── navigation/      # Navigation structure
│   │   └── AppNavigator.tsx
│   ├── services/        # API and WebSocket clients
│   │   ├── api.ts
│   │   └── websocket.ts
│   ├── stores/          # Zustand state stores
│   │   ├── auth.ts
│   │   ├── chat.ts
│   │   └── settings.ts
│   ├── types/           # TypeScript type definitions
│   │   └── api.ts
│   └── utils/           # Theme and utilities
│       └── theme.ts
├── app.json
├── babel.config.js
├── package.json
└── tsconfig.json
```

## Features
- **Chat**: Real-time conversation with Jarvis via WebSocket
- **Knowledge**: Browse knowledge digests and feeds
- **Testing**: View test plans and runs from the SaaS testing service
- **Freelance**: Browse available tasks and view job history
- **Plugins**: Manage installed plugins
- **Settings**: Configure API URL, theme, profile

## API
All API calls use the shared backend at `http://localhost:8000/api/v1/`.
Configure the API URL in Settings.