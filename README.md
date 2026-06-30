# Jarvis

Jarvis is a modular, local-first AI assistant platform that combines voice, text, and API interactions with a powerful tool/plugin system.

## Features

- **Core Chat**: Real-time communication with LLMs.
- **Tool Execution**: Integrated tools for file operations, web search, and more.
- **Desktop App**: Electron-based interface for a seamless experience.
- **Local-First**: Built with privacy and speed in mind.

## Architecture

The project is divided into two main components:

### Backend (FastAPI)
- **API**: Handles authentication, chat, and tool execution.
- **Models**: PostgreSQL for persistent storage.
- **Cache**: Redis for session management and performance.
- **LLM Integration**: Seamless connection to various LLM providers (OpenAI, etc.).

### Frontend (Electron + React)
- **UI**: Modern, responsive interface built with React and Tailwind CSS.
- **IPC**: Secure communication between the main and renderer processes.
- **State Management**: Zustand for global state.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js (for frontend development)
- Python 3.12 (for backend development)

### Running with Docker

1. Clone the repository:
   ```bash
   git clone https://github.com/abdunnooor01-boop/Jarvis.git
   cd Jarvis
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

3. Start the services:
   ```bash
   docker compose up --build
   ```

The backend will be available at `http://localhost:8000`.

### Development Setup

Refer to the individual `README.md` files in `backend/` and `frontend/` (if available) for specific development instructions.

## Testing

A comprehensive test strategy is documented in `test-strategy.md`.

To run backend tests:
```bash
cd backend
pytest
```

To run frontend tests:
```bash
cd frontend
npm test
```
