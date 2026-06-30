# Jarvis AI Assistant — Testing Strategy & Plan

> **Author:** QA Engineer  
> **Date:** 2026-06-30  
> **Status:** Draft  
> **Version:** 1.0  

---

## Table of Contents

1. [Test Pyramid & Coverage Targets](#1-test-pyramid--coverage-targets)
2. [Backend Testing Plan](#2-backend-testing-plan)
3. [Frontend Testing Plan](#3-frontend-testing-plan)
4. [Voice Testing Plan](#4-voice-testing-plan)
5. [Security Testing](#5-security-testing)
6. [Performance Testing](#6-performance-testing)
7. [Automation Setup](#7-automation-setup)
8. [Test Data & Fixtures](#8-test-data--fixtures)
9. [CI/CD Integration](#9-cicd-integration)
10. [Phase-by-Phase Rollout](#10-phase-by-phase-rollout)

---

## 1. Test Pyramid & Coverage Targets

### 1.1 Test Pyramid

```
         ╱╲
        ╱  ╲
       ╱ E2E╲           ← 5% — Critical user journeys (Playwright)
      ╱──────╲
     ╱Integration╲      ← 20% — API, WebSocket, DB (pytest + httpx)
    ╱────────────╲
   ╱   Unit Tests   ╲   ← 75% — Services, models, schemas, components
  ╱──────────────────╲
```

### 1.2 Coverage Targets

| Layer | Target | Minimum | Tools |
|-------|--------|---------|-------|
| **Backend core services** (auth, LLM, memory) | 95% | 90% | `pytest-cov` |
| **Backend API routes** | 95% | 90% | `pytest-cov` + `httpx` |
| **Backend models/schemas** | 95% | 90% | `pytest-cov` |
| **Frontend components** | 85% | 80% | `vitest` + `@testing-library/react` |
| **Frontend stores** (Zustand) | 95% | 90% | `vitest` |
| **Frontend hooks** | 90% | 85% | `vitest` + `@testing-library/react-hooks` |
| **E2E critical paths** | 100% coverage of paths | — | `Playwright` |
| **Overall project** | 90% | 85% | Combined |

### 1.3 Priority Definitions

| Priority | Meaning |
|----------|---------|
| **P0** | Blocking — must pass before any release. Core functionality, auth, data integrity. |
| **P1** | Critical — high business impact. Should be tested but doesn't block emergency fixes. |
| **P2** | Important — nice to have automated. Manual testing acceptable temporarily. |
| **P3** | Nice-to-have — edge cases, visual polish, accessibility deep-dives. |

---

## 2. Backend Testing Plan

### 2.1 Current State

The backend at `/home/team/shared/jarvis/backend/` has:
- Config, database engine, core auth utilities, dependencies, logging
- SQLAlchemy models (User, Conversation, Message)
- Pydantic schemas (auth, chat)
- **No API routes, services, WebSocket handlers, or tests yet**

### 2.2 Testing Stack

| Component | Tool |
|-----------|------|
| Test runner | pytest 8.3+ |
| Async support | pytest-asyncio (auto mode) |
| Coverage | pytest-cov |
| HTTP client | httpx (AsyncClient) |
| Database | aiosqlite (in-memory SQLite for tests) |
| Mocking | unittest.mock + pytest-mock |
| Factories | factory_boy (recommended add) |

### 2.3 Auth Tests (P0)

**What to test:**
- `hash_password()` / `verify_password()` — correct hash, wrong password, empty string, Unicode
- `create_access_token()` / `create_refresh_token()` — valid creation, expiry, payload structure
- `decode_token()` — valid token, expired token, malformed token, wrong algorithm, tampered payload
- Token type validation — access vs refresh, type mismatch rejection
- Token edge cases — empty string, None, JWT with invalid signatures
- `get_current_user()` dependency — valid token, missing header, expired token, soft-deleted user, wrong token type
- `get_optional_user()` — no token returns None, invalid token returns None, valid token returns user

**How to test:**
- Unit tests for `core/auth.py` — pure functions, direct calls
- Async integration via test client for dependency injection
- Use `TestClient` (httpx with `ASGITransport`) for endpoint-level auth tests
- Mock `get_db` to return a test session with known user data

**Success criteria:**
- All auth functions have 100% branch coverage
- Every JWT error path returns the correct HTTP 401 with RFC-compliant body
- Token creation and validation are deterministic given fixed inputs

**Priority:** P0

### 2.4 API Endpoint Tests (P0-P1)

**Endpoints to test (once implemented):**

| Endpoint | Method | Priority | Key Test Cases |
|----------|--------|----------|----------------|
| `/api/v1/auth/register` | POST | P0 | Valid registration, duplicate email, weak password, missing fields |
| `/api/v1/auth/login` | POST | P0 | Valid login, wrong password, non-existent user, rate-limited |
| `/api/v1/auth/refresh` | POST | P0 | Valid refresh, expired refresh, revoked token |
| `/api/v1/auth/me` | GET | P0 | Authenticated, unauthenticated, deleted user |
| `/api/v1/conversations` | GET | P1 | List own conversations, pagination, empty list, auth required |
| `/api/v1/conversations` | POST | P1 | Create, validation, auth required |
| `/api/v1/conversations/{id}` | GET | P1 | Own conversation, other user's (403), not found, deleted |
| `/api/v1/conversations/{id}` | DELETE | P1 | Soft delete, hard delete, not owner, not found |
| `/api/v1/conversations/{id}/messages` | GET | P1 | List messages, pagination, empty conversation |
| `/api/v1/admin/*` | GET/POST | P1 | Admin-only access, non-admin 403, missing auth |

**How to test:**
- Use `httpx.AsyncClient` with `ASGITransport` wrapping the FastAPI app
- Override dependencies (database, auth) with test doubles
- Create fixture-based test users with known states
- Test each endpoint with: valid input, invalid input, missing auth, wrong auth, edge values

**Success criteria:**
- Every endpoint has tests for: happy path, auth failure, input validation failure, and not-found
- Paginated endpoints tested for boundary values (page=0, page=1, beyond-last)
- All CRUD operations tested end-to-end through API layer

**Priority:** P0 for auth endpoints, P1 for conversations

### 2.5 WebSocket Chat Tests (P0)

**What to test:**
- Connection with valid auth token
- Connection with invalid/expired/missing token → rejected
- Send message with valid `ChatMessageRequest`
- Receive streamed response tokens
- Create new conversation via WebSocket (no `conversation_id` sent)
- Continue existing conversation via `conversation_id`
- Handle conversation_id pointing to non-existent/deleted conversation
- Handle conversation_id belonging to another user → rejected
- Send empty message → validation error
- Very long message (boundary)
- Concurrent WebSocket connections for same user
- Disconnect mid-stream → cleanup
- Rate limiting on WebSocket messages
- Reconnection with same conversation context

**How to test:**
- Use `httpx` and `websockets` library for WebSocket client
- Create a test FastAPI app with overridden dependencies
- Mock the LLM service to return controlled streaming responses
- Test authentication handshake before WebSocket upgrade
- Use `pytest-asyncio` for async WebSocket I/O

**Success criteria:**
- All chat flows (new conversation, existing conversation, streaming) covered
- Auth rejection tested for every invalid-token variant
- Error responses are structured (RFC 7807) and non-blocking
- Stream interruption doesn't leave stale state

**Priority:** P0

### 2.6 LLM Service Tests (P0)

**What to test:**
- Provider selection logic (OpenAI, Anthropic, Gemini, local)
- Response streaming — token-by-token delivery
- Response non-streaming — complete response
- Error handling — API timeout, rate limit, invalid API key, model unavailable
- Context window management — truncation strategy, max tokens
- Tool call initiation — LLM requests tool → tool executes → result sent back
- Multi-turn conversation context building
- Mock ALL providers — never call real APIs in CI

**How to test:**
- Define mock fixtures for each LLM provider returning controlled responses
- Use `pytest.mark.parametrize` to test across providers
- Test error handling via mock that raises specific exceptions
- Verify the service handles provider failover (primary down → secondary)
- Use dependency injection so `LLMService` never touches real APIs in tests

**Success criteria:**
- Every provider adapter tested with: success (streaming + non-streaming), timeout, auth error, server error
- Context window truncation tested at boundary (just under, at, just over limit)
- Tool calling round-trip tested end-to-end with mock tools
- No real API key needed in CI — all tests pass with mocks

**Priority:** P0

### 2.7 Tool Execution Tests (P1)

**What to test:**
- Base tool class — interface contract, parameter validation
- `web_search` — mock HTTP responses, handle network errors, rate limits, empty results
- `file_ops` — mock filesystem, test read/write/delete within allowed paths, path traversal prevention
- `clipboard` — mock clipboard API, test read/write
- `terminal` — mock subprocess, test command execution, timeout, sandbox escape prevention
- Tool authorization — user-specific tool permissions
- Tool execution timeout — long-running tool killed gracefully
- Tool chain — multiple tools called in sequence within one conversation turn
- Plugin-loaded tools — dynamic loading, validation, security sandbox

**How to test:**
- Use `unittest.mock` (or `pytest-monkeypatch`) to replace filesystem, network, subprocess
- Each tool gets a dedicated test file in `tests/test_tools/`
- Test path traversal by attempting `../../etc/passwd` patterns
- Test subprocess sandbox: attempt shell injection in command arguments
- Test timeout via a tool that sleeps longer than the configured timeout

**Success criteria:**
- Every tool has: happy path, failure mode, and security boundary tests
- Path traversal attacks blocked in file_ops
- Shell injection blocked in terminal tool
- Timeout kills execution and returns clean error
- Plugin-loaded tools validate schema before loading

**Priority:** P1

### 2.8 Database Tests (P1)

**What to test:**
- Model definitions match schema — columns, types, constraints, defaults
- User creation — all fields populated correctly, UUID auto-generation
- Conversation creation — FK relationship to User, cascade delete
- Message creation — FK to Conversation, ordering by `created_at`
- Soft delete — `deleted_at` set, query filtering for active records
- Unique constraint — duplicate email raises integrity error
- Cascade behavior — deleting user deletes conversations and messages
- Model `__repr__` methods

**How to test:**
- Use `aiosqlite` with SQLAlchemy's `create_async_engine("sqlite+aiosqlite://")` for tests
- Create tables from models, run operations, verify state
- Test constraints by attempting to insert invalid data
- Use transaction rollback between tests for isolation
- Factory functions create test data with minimal boilerplate

**Note:** SQLite differs from PostgreSQL in some constraint behavior. Use a separate CI job that runs against a real PostgreSQL (via service container or testcontainers) for full fidelity.

**Success criteria:**
- All model relationships tested (create, read, cascade delete)
- Unique/not-null constraints validated
- Soft-delete queries correctly filter
- In-memory SQLite tests fast (<100ms per test)

**Priority:** P1

### 2.9 Rate Limiting Tests (P1)

**What to test:**
- Chat endpoint: 100 req/min per user — 99th request succeeds, 101st blocked
- API endpoint: 1000 req/min per user — boundary test
- Different users have independent rate limit counters
- Rate limit resets after the window expires
- Rate limit headers present in response (`X-RateLimit-Remaining`, `X-RateLimit-Reset`)
- WebSocket message rate limiting
- Rate limit bypass via IP spoofing (X-Forwarded-For manipulation)

**How to test:**
- Mock Redis with fakeredis or an in-memory Redis replacement
- Create a test that fires N requests in rapid succession and checks the N+1th is blocked
- Test with multiple user tokens to confirm independent counters
- Use `time` manipulation (`monkeypatch` / `freezegun`) to test window expiry without wall-clock waits

**Success criteria:**
- Exactly at limit: allowed; one over: blocked with 429
- Rate limit info returned in response headers
- Different users don't affect each other's counters
- WebSocket rate limit enforced per connection

**Priority:** P1

---

## 3. Frontend Testing Plan

### 3.1 Current State

The frontend at `/home/team/shared/jarvis/frontend/` has:
- Electron main process (window creation, lifecycle)
- Preload script with context bridge
- React renderer entry point + App component
- Zustand auth store
- **No tests configured yet**
- **No testing dependencies in package.json**

### 3.2 Testing Stack (to be added)

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `vitest` | ^2.0 | Test runner (Vite-native) |
| `@testing-library/react` | ^16.0 | React component testing |
| `@testing-library/jest-dom` | ^6.0 | Custom DOM matchers |
| `@testing-library/user-event` | ^14.0 | User interaction simulation |
| `jsdom` | ^25.0 | DOM environment for tests |
| `msw` | ^2.0 | API mocking (HTTP + WebSocket) |
| `@playwright/test` | ^1.48 | E2E testing |
| `axe-core` + `@axe-core/playwright` | ^4.10 | Accessibility testing |

### 3.3 Component Tests (P1)

**Components to test (once implemented):**

| Component | Priority | Key Test Cases |
|-----------|----------|----------------|
| `ChatWindow` | P0 | Renders messages, sends new message, shows typing indicator, scrolls to bottom |
| `MessageBubble` | P1 | Renders user vs assistant styling, code blocks, markdown, long messages |
| `VoiceButton` | P1 | Start/stop recording, permission denied, permission granted, disabled state |
| `AssistantAvatar` | P2 | Different states (thinking, speaking, idle), animation triggers |
| `SettingsPanel` | P1 | Render settings, save changes, cancel, reset to defaults |
| `Notification` | P2 | Show/hide, click action, dismiss, multiple notifications |
| `LoginForm` | P0 | Valid submission, validation errors, loading state, disabled button |
| `RegisterForm` | P0 | Valid submission, password mismatch, email format, existing email error |
| `ConversationList` | P1 | Renders list, empty state, selected state, click to switch |

**How to test:**
- Render components with `@testing-library/react`
- Use `userEvent` for interactions (typing, clicking)
- Mock Zustand stores with `useAuthStore.setState()` before render
- Test loading, error, and empty states explicitly
- Verify accessibility attributes with `jest-axe`

**Success criteria:**
- Each component renders without crashing in all states (loading, empty, error, populated)
- User interactions produce correct state changes
- Accessibility violations below threshold
- No console errors during rendering

**Priority:** P0 for ChatWindow/Login/Register, P1 for others

### 3.4 State Management Tests (P0)

**Stores to test:**

| Store | Priority | Key Test Cases |
|-------|----------|----------------|
| `auth.ts` | P0 | `setAuth` stores token + user, `logout` clears everything, persist across re-renders |
| `chat.ts` | P1 | Add message, clear messages, set active conversation, streaming token append |
| `settings.ts` | P1 | Update setting, reset to defaults, partial update, type validation |
| `voice.ts` | P1 | Recording state transitions, audio blob storage, error state |

**How to test:**
- Use `vitest` with the Zustand store directly (no DOM needed)
- Test each action (setter) produces the expected state
- Test edge cases: `setAuth(null, null)`, `logout()` when already logged out
- Test derived state via selectors
- Test async actions (e.g., `chat.ts` sending a message via WebSocket)

**Success criteria:**
- Every store action tested with valid and invalid inputs
- State transitions are pure and deterministic
- No stale or orphaned state after cleanup actions

**Priority:** P0

### 3.5 Hook Tests (P1)

**Hooks to test (once implemented):**

| Hook | Priority | Key Test Cases |
|------|----------|----------------|
| `useWebSocket` | P0 | Connect, disconnect, reconnect on drop, message receive, send, auth token refresh |
| `useVoiceRecorder` | P1 | Start recording, stop recording, audio data callback, permission denied, browser support |

**How to test:**
- Render hooks in test components with `renderHook` from `@testing-library/react`
- Mock WebSocket using `msw` or a simple EventEmitter-based mock
- Mock `MediaRecorder` and `navigator.mediaDevices.getUserMedia`
- Test reconnection: close WebSocket, verify auto-reconnect fires
- Test concurrent hook instances (multiple WS connections)

**Success criteria:**
- WebSocket hook handles connect/disconnect/reconnect/error cycles
- Voice hook handles permission grant/deny and produces valid audio blobs
- All subscriptions cleaned up on unmount (no memory leaks)

**Priority:** P0 for useWebSocket, P1 for useVoiceRecorder

### 3.6 E2E Tests (Playwright) (P0)

**Critical paths to test:**

| Flow | Priority | Steps |
|------|----------|-------|
| **Login → Chat → Response** | P0 | Open app → see login → enter credentials → see chat window → type message → receive response stream → see message in history |
| **Registration → Auto-login → Chat** | P0 | Open app → register → auto-logged in → create conversation → send message → logout |
| **Settings → Theme toggle** | P1 | Login → open settings → toggle dark mode → verify theme persists → reload → verify theme persists |
| **Voice recording → Playback** | P1 | Login → press voice button → record → stop → verify audio sent → see transcribed message |
| **Conversation history** | P1 | Login → create 2 conversations → switch between them → verify messages load correctly |
| **Token expiry → Re-login** | P1 | Login → wait for token expiry (simulate) → attempt action → redirected to login → re-login → continue where left off |
| **Window management** | P2 | Open → close → reopen → verify state restored |

**How to test:**
- Use `@playwright/test` with Electron support
- Configure Playwright to launch the Electron app
- Use codegen for initial path recording, then refine
- Run against a test backend instance (Docker Compose with test data)
- Use `page.route()` to intercept and mock LLM streaming for deterministic E2E tests
- Test in headless mode in CI, headed mode for debugging

**Success criteria:**
- All P0 flows pass on every PR
- P1 flows pass before release
- E2E tests complete in under 5 minutes total
- Tests are deterministic (no flaky timeouts)

**Priority:** P0

### 3.7 Electron-Specific Tests (P2)

**What to test:**
- Window creation — correct size, title bar style, preload script loaded
- App lifecycle — ready, activate (macOS re-open), window-all-closed (quit on non-macOS)
- IPC communication — main ↔ renderer message passing
- Native notifications — trigger, permissions, click handler
- System tray (if implemented) — show/hide, context menu
- Auto-updater (if implemented) — update check, download, install
- Application menu — custom menus, keyboard shortcuts

**How to test:**
- Use Playwright's Electron support (`_electron.launch()`)
- Use Spectron alternatives or direct `electron` APIs
- Test IPC by invoking handlers and verifying main process response

**Success criteria:**
- Window opens with correct dimensions and preload
- App quits correctly on all platforms
- IPC round-trips work without errors

**Priority:** P2

### 3.8 Accessibility Tests (P2)

**What to test:**
- All interactive elements have accessible names
- Color contrast meets WCAG AA standards
- Keyboard navigation — tab order, focus indicators, enter/space activation
- Screen reader support — ARIA labels, live regions for chat updates
- Focus management — modal dialogs trap focus, chat input auto-focused
- Reduced motion — respect `prefers-reduced-motion`
- Dark/light mode contrast in both themes

**How to test:**
- Use `axe-core` with Playwright (`@axe-core/playwright`) for automated scans
- Use `jest-axe` for component-level analysis
- Manual testing with VoiceOver (macOS) / NVDA (Windows)
- Run CI checks that fail on critical violations

**Success criteria:**
- Zero critical/severe axe violations in CI
- All interactive elements keyboard-accessible
- Chat content is announced to screen readers when new messages arrive

**Priority:** P2

---

## 4. Voice Testing Plan

### 4.1 Speech-to-Text (STT) Tests (P1)

**What to test:**
- Whisper STT accuracy — target Word Error Rate (WER) < 5% for clean audio, < 15% for noisy
- Audio format handling — WAV, MP3, OGG, FLAC
- Audio length limits — very short (<1s), very long (>5min), empty audio
- Language detection — English primary, multilingual fallback
- Background noise handling — varying SNR levels
- Punctuation and capitalization restoration
- Streaming STT — incremental transcription as audio arrives
- Error handling — corrupted audio, unsupported codec, server timeout

**How to test:**
- Create a test dataset of reference audio files with known transcripts
- Measure WER against reference transcripts
- Use `pytest` parametrization over audio conditions
- Mock Whisper API for CI tests; run full accuracy suite nightly

**Success criteria:**
- WER targets met on reference dataset
- All supported formats process without error
- Corrupted/empty audio returns structured error, not crash

**Priority:** P1

### 4.2 Text-to-Speech (TTS) Tests (P1)

**What to test:**
- Audio generation — valid WAV/MP3 output, correct sample rate
- Voice selection — multiple voices available, voice switch works
- SSML support — prosody, emphasis, breaks
- Streaming playback — audio chunk delivery during generation
- Edge cases — empty text, very long text (>5000 chars), special characters
- Error handling — network failure, invalid voice ID, rate limit

**How to test:**
- Generate audio from known text, verify output format and metadata
- Check audio duration is roughly proportional to input length
- Mock TTS provider for CI; verify output shape without real audio
- Test SSML by providing valid and invalid markup

**Success criteria:**
- Valid audio output for all supported texts
- Audio properties (sample rate, channels, bit depth) match config
- SSML markup correctly influences output (verified via duration/spectrogram)

**Priority:** P1

### 4.3 Wake Word Detection Tests (P2)

**What to test:**
- Wake word detection rate — >95% for primary wake word
- False positive rate — <1 false activation per hour
- False negative rate — <5% miss rate at normal speaking volume
- Background noise rejection — TV, music, conversation in room
- Multiple wake words — switching between them
- Accent variation — tested with 5+ accent groups
- Volume sensitivity — whisper vs normal vs loud
- Cooldown period — no re-trigger within N seconds

**How to test:**
- Collect a diverse dataset of wake word utterances (different accents, volumes, backgrounds)
- Measure true positive, false positive, false negative rates
- Run automated detection tests with pre-recorded audio clips
- Use CI with recorded samples; full accent diversity tested on a schedule

**Success criteria:**
- >95% detection rate at normal volume
- <1 false positive per simulated hour
- Passes with 5+ accent groups at >90% detection

**Priority:** P2

### 4.4 Noise Handling Tests (P2)

**What to test:**
- Noise suppression — VAD (Voice Activity Detection) accuracy
- Echo cancellation — hands-free operation quality
- Audio preprocessing — normalization, noise gate, compression
- Extreme conditions — wind noise, fan noise, crowded room, phone speaker

**How to test:**
- Mix clean speech with noise at various SNR levels (0dB to 20dB)
- Measure STT accuracy with and without noise suppression
- Test with standardized noise profiles (NOISEX-92 dataset or similar)

**Success criteria:**
- STT accuracy degradation <20% at 10dB SNR vs clean
- VAD correctly classifies speech vs silence at >95% accuracy

**Priority:** P2

### 4.5 Accent Diversity Testing (P2)

**What to test:**
- STT accuracy across accent groups (US, UK, Indian, Australian, Spanish-accented, Mandarin-accented, French-accented)
- TTS voice naturalness for non-English names/words
- Wake word detection across accents

**How to test:**
- Create test dataset with 7+ accent groups, minimum 50 utterances each
- Measure WER per accent group
- Flag accent groups below accuracy threshold for model fine-tuning

**Success criteria:**
- Maximum WER differential between best and worst accent <10%
- All accent groups >80% STT accuracy

**Priority:** P2

---

## 5. Security Testing

### 5.1 Authentication Security (P0)

| Test | Method | Success Criteria |
|------|--------|-----------------|
| Auth bypass on all endpoints | Attempt all API routes without token | All return 401 |
| Token replay | Capture valid token, reuse from different IP | Configurable: reject or allow with risk scoring |
| Token tampering | Modify JWT payload (change sub, exp) | JWT signature validation catches |
| Token theft via XSS | Inject script to steal token from localStorage | HttpOnly cookies; CSP prevents |
| Refresh token rotation | Use refresh token, old one invalidated | Yes |
| Brute force login | N rapid attempts | Lockout after 5 failures, rate limiting |
| Password complexity | Verify min 8 chars, reject common patterns | Policy enforced at schema + service level |
| Registration with existing email | Attempt duplicate | Returns 409 Conflict |

### 5.2 Input Validation (P0)

| Test | Method | Success Criteria |
|------|--------|-----------------|
| SQL injection in chat messages | Send `'; DROP TABLE users; --` as message content | Parametrized queries prevent injection |
| SQL injection in IDs | Send SQL in URL path params | UUID validation rejects |
| XSS in chat messages | Send `<script>alert('xss')</script>` | Content sanitized before render |
| XSS in display name | Register with `<img onerror=...>` | Sanitized on output |
| SSRF in LLM tool calls | Tool that fetches URL like `http://169.254.169.254/` | Tool URL allow-list enforced |
| Path traversal in file tool | `../../../etc/passwd` | Tool sandbox prevents escape |
| Large payloads | 10MB chat message | Payload size limited |
| Prototype pollution | Send `__proto__` in JSON body | Input validation rejects |

### 5.3 Rate Limit Security (P1)

| Test | Method | Success Criteria |
|------|--------|-----------------|
| Rate limit bypass via header spoofing | Add/multiple X-Forwarded-For headers | Rate limiter uses authenticated user, not IP |
| Rate limit bypass via token cycling | Create N tokens, use each once | Rate limits per user across all tokens |
| Distributed brute force | Slow attack from many IPs | Per-user lockout, anomaly detection |
| Rate limit on auth vs API | Verify different limits apply | Chat: 100/min, General API: 1000/min |

### 5.4 Tool Execution Security (P1)

| Test | Method | Success Criteria |
|------|--------|-----------------|
| Sandbox escape in terminal tool | `cat /etc/shadow` | Sandbox restricts to allowed dirs |
| Command injection | `; rm -rf /` | Shell arguments escaped |
| Fork bomb prevention | Tool that spawns infinite subprocesses | Process limits enforced |
| File system access | Read/write outside allowed paths | Restricted |
| Network access from tool | Tool calling internal services | Network sandbox |

### 5.5 WebSocket Security (P0)

| Test | Method | Success Criteria |
|------|--------|-----------------|
| Unauthenticated connection | Connect without token | Rejected before upgrade |
| Token expiry mid-session | Wait for expiry, send message | Server closes connection with 4001 |
| Conversation access control | Connect to another user's conversation | 403 error |
| Message injection | Send malformed JSON | Pydantic validation rejects |
| DoS via rapid messages | 1000 messages/second | Rate limiting closes connection |

### 5.6 Additional Security (P2)

| Test | Priority | Method |
|------|----------|--------|
| Dependency scanning | P1 | `pip audit`, `npm audit` in CI |
| Secret scanning | P1 | `truffleHog` / `git-secrets` pre-commit hook |
| CORS misconfiguration | P0 | Verify only allowed origins |
| Security headers | P1 | CSP, HSTS, X-Frame-Options, X-Content-Type-Options present |
| CSRF (if cookie auth added) | P1 | Double-submit cookie or SameSite=Strict |

---

## 6. Performance Testing

### 6.1 Chat Latency (P1)

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first token (p95) | <500ms | From message send to first stream chunk |
| Time to first token (p99) | <1s | From message send to first stream chunk |
| Total response time (p95) | <5s for 500-token response | Full response receipt |
| WebSocket connection time | <200ms | Handshake to ready state |

**Tools:** Locust or k6 for load generation, application-level timing instrumentation

**Method:**
- Deploy backend to staging environment with realistic resources
- Run load test with 10, 50, 100, 200 concurrent users
- Measure latency percentiles at each concurrency level
- Run with and without memory/tool integration to identify bottlenecks

**Priority:** P1

### 6.2 WebSocket Concurrent Connections (P1)

| Metric | Target |
|--------|--------|
| Max concurrent connections | 1000 without degradation |
| Connection ramp-up | 100 connections/second |
| Sustained connections | 500 for 30 minutes |

**Tools:** k6 with WebSocket extension, custom connection pool

**Method:**
- Connect N virtual users via WebSocket
- Send periodic keepalive messages
- Measure connection stability, memory, CPU
- Identify leak patterns (connections not cleaned up on disconnect)

**Priority:** P1

### 6.3 Memory & CPU Profiling (P2)

| Metric | Target |
|--------|--------|
| Backend memory per 100 concurrent sessions | <500MB RSS |
| Frontend memory (idle) | <200MB |
| Frontend memory (chatting, 1000 messages) | <350MB |
| CPU usage during streaming | <1 core per 50 concurrent streams |

**Tools:** `memory_profiler`, `py-spy` (Python), Chrome DevTools Memory/Performance tabs (Electron)

**Method:**
- Profile backend with increasing load, identify memory growth patterns
- Profile frontend with long chat sessions, verify no leaks
- Run Electron with `--inspect` and capture heap snapshots

**Priority:** P2

### 6.4 Database Query Performance (P2)

| Query | Target (p95) |
|-------|-------------|
| Load user conversations (list) | <50ms with 1000 conversations |
| Load conversation with messages | <100ms with 5000 messages |
| Memory search (pgvector, 10K vectors) | <200ms |
| Insert message | <10ms |

**Tools:** `pg_stat_statements`, EXPLAIN ANALYZE, application-level query timing

**Method:**
- Seed database with realistic data volumes
- Run each query type 1000 times, measure percentiles
- Identify missing indexes via slow query log
- Test with and without pgvector index (IVFFlat, HNSW)

**Priority:** P2

### 6.5 LLM Streaming Throughput (P1)

| Metric | Target |
|--------|--------|
| Tokens per second (streaming) | >50 tokens/s (OpenAI GPT-4o) |
| Concurrent LLM calls per instance | 10 without degradation |
| Provider failover time | <2s |

**Tools:** Custom benchmark scripts, mocked LLM endpoints for controlled testing

**Method:**
- Measure throughput with real (in staging) and mocked LLM endpoints
- Test concurrency by sending simultaneous chat messages
- Test provider failover by having primary provider return errors

**Priority:** P1

---

## 7. Automation Setup

### 7.1 Backend Testing Configuration

**pytest configuration** (already partially set up in `pyproject.toml`):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

**Recommended additions to `pyproject.toml`:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:alembic.*",
    "ignore::DeprecationWarning:jose.*",
]

[tool.coverage.run]
source = ["app"]
omit = ["app/plugins/*", "*/tests/*", "*/migrations/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
fail_under = 90
```

**Directory structure required:**

```
backend/tests/
├── conftest.py              # Global fixtures (db session, test client, auth headers)
├── factory.py               # Factory functions for test data
├── test_api/
│   ├── test_auth.py
│   ├── test_conversations.py
│   ├── test_messages.py
│   ├── test_admin.py
│   └── test_websocket.py
├── test_services/
│   ├── test_llm.py
│   ├── test_memory.py
│   ├── test_voice.py
│   ├── test_tool_executor.py
│   └── test_task_scheduler.py
├── test_models/
│   ├── test_user.py
│   ├── test_conversation.py
│   └── test_message.py
├── test_tools/
│   ├── test_base.py
│   ├── test_web_search.py
│   ├── test_file_ops.py
│   ├── test_clipboard.py
│   └── test_terminal.py
├── test_core/
│   ├── test_auth.py
│   ├── test_dependencies.py
│   └── test_logging.py
├── fixtures/
│   ├── llm_responses.py     # Mock LLM response data
│   ├── audio_samples.py     # Audio test data helpers
│   └── conversations.py     # Sample conversation scenarios
└── conftest_db.py           # Database-specific fixtures (SQLite + PostgreSQL)
```

### 7.2 Frontend Testing Configuration

**Add to `package.json`:**

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "test:e2e": "playwright test",
    "test:e2e:debug": "playwright test --debug",
    "test:accessibility": "playwright test --grep @a11y"
  },
  "devDependencies": {
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/user-event": "^14.0.0",
    "jsdom": "^25.0.0",
    "msw": "^2.0.0",
    "@playwright/test": "^1.48.0",
    "axe-core": "^4.10.0",
    "@axe-core/playwright": "^4.10.0"
  }
}
```

**`vitest.config.ts` (new file):**

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/renderer/**/*.{ts,tsx}'],
      exclude: [
        'src/renderer/main.tsx',
        '**/*.d.ts',
        '**/*.test.*',
        '**/node_modules/**',
      ],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
    },
  },
  resolve: {
    alias: {
      '@renderer': path.resolve(__dirname, 'src/renderer'),
      '@shared': path.resolve(__dirname, 'src/shared'),
    },
  },
})
```

**`tests/setup.ts` (new file):**

```typescript
import '@testing-library/jest-dom'
```

**`playwright.config.ts` (new file):**

```typescript
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'electron',
      use: {
        // Electron app configuration
        browserName: 'chromium',
        launchOptions: {
          executablePath: '/path/to/electron',
        },
      },
    },
  ],
})
```

**Frontend test directory structure:**

```
frontend/tests/
├── setup.ts                    # Test setup (jest-dom matchers, MSW handlers)
├── unit/
│   ├── components/
│   │   ├── ChatWindow.test.tsx
│   │   ├── VoiceButton.test.tsx
│   │   ├── LoginForm.test.tsx
│   │   └── SettingsPanel.test.tsx
│   ├── stores/
│   │   ├── auth.test.ts
│   │   ├── chat.test.ts
│   │   └── settings.test.ts
│   └── hooks/
│       ├── useWebSocket.test.ts
│       └── useVoiceRecorder.test.ts
├── e2e/
│   ├── login.spec.ts
│   ├── chat.spec.ts
│   ├── settings.spec.ts
│   └── voice.spec.ts
└── fixtures/
    ├── mockHandlers.ts
    └── testData.ts
```

### 7.3 CI Pipeline (GitHub Actions)

**`.github/workflows/test.yml` configuration:**

```yaml
name: Test Suite

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [develop]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          
      - name: Install backend deps
        run: pip install -r backend/requirements-dev.txt
        
      - name: Ruff lint
        run: cd backend && ruff check .
        
      - name: Ruff format check
        run: cd backend && ruff format --check .
        
      - name: mypy
        run: cd backend && mypy app/
        
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install frontend deps
        run: cd frontend && npm ci
        
      - name: TypeScript check
        run: cd frontend && npx tsc --noEmit

  test-backend:
    name: Backend Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: jarvis
          POSTGRES_PASSWORD: jarvis
          POSTGRES_DB: jarvis_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          
      - name: Install deps
        run: pip install -r backend/requirements-dev.txt
        
      - name: Run tests (SQLite)
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=term --cov-report=xml --cov-fail-under=90
        
      - name: Run tests (PostgreSQL)
        env:
          TEST_DATABASE_URL: postgresql+asyncpg://jarvis:jarvis@localhost:5432/jarvis_test
        run: |
          cd backend
          pytest tests/ -v -m "postgres" --cov=app --cov-report=term
          
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./backend/coverage.xml

  test-frontend:
    name: Frontend Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install deps
        run: cd frontend && npm ci
        
      - name: Unit tests
        run: cd frontend && npx vitest run --coverage
        
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./frontend/coverage/coverage-final.json
          
      - name: Store Playwright artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report/

  test-e2e:
    name: E2E Tests
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Install deps
        run: cd frontend && npm ci
        
      - name: Install Playwright browsers
        run: cd frontend && npx playwright install --with-deps chromium
        
      - name: Start backend
        run: |
          cd backend
          # Start test server with mock LLM
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          
      - name: Run E2E tests
        run: cd frontend && npx playwright test
        
      - name: Upload test results
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-results
          path: frontend/test-results/

  required-checks:
    name: Required Checks
    if: always()
    needs: [lint, test-backend, test-frontend, test-e2e]
    runs-on: ubuntu-latest
    steps:
      - run: |
          echo "Lint: ${{ needs.lint.result }}"
          echo "Backend Tests: ${{ needs.test-backend.result }}"
          echo "Frontend Tests: ${{ needs.test-frontend.result }}"
          echo "E2E Tests: ${{ needs.test-e2e.result }}"
          if [ "${{ needs.lint.result }}" != "success" ] || \
             [ "${{ needs.test-backend.result }}" != "success" ] || \
             [ "${{ needs.test-frontend.result }}" != "success" ] || \
             [ "${{ needs.test-e2e.result }}" != "success" ]; then
            exit 1
          fi
```

### 7.4 Pre-commit Hooks

**`.pre-commit-config.yaml` additions:**

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.3
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: [--strict]
        files: ^backend/
        additional_dependencies: [pydantic, sqlalchemy]

  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest (quick)
        entry: cd backend && pytest tests/ -x -q --no-header -m "not slow"
        language: system
        types: [python]
        pass_filenames: false
        
      - id: vitest-quick
        name: vitest (quick)
        entry: cd frontend && npx vitest run --changed
        language: system
        files: ^frontend/src/
        pass_filenames: false

  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### 7.5 Mock Fixtures for LLM Providers

**`backend/tests/fixtures/llm_responses.py`:**

```python
"""Mock LLM responses for testing."""

# Standard chat completion response (non-streaming)
MOCK_CHAT_RESPONSE = {
    "id": "chatcmpl-mock-123",
    "object": "chat.completion",
    "created": 1700000000,
    "model": "gpt-4o-mock",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "Hello! I'm Jarvis, your AI assistant. How can I help you today?",
        },
        "finish_reason": "stop",
    }],
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 15,
        "total_tokens": 65,
    },
}

# Streaming response chunks
MOCK_STREAM_CHUNKS = [
    {"choices": [{"delta": {"role": "assistant"}, "index": 0}]},
    {"choices": [{"delta": {"content": "Hello"}, "index": 0}]},
    {"choices": [{"delta": {"content": "! I"}, "index": 0}]},
    {"choices": [{"delta": {"content": " am"}, "index": 0}]},
    {"choices": [{"delta": {"content": " Jarvis"}, "index": 0}]},
    {"choices": [{"delta": {"content": "."}, "index": 0}]},
    {"choices": [{"delta": {}, "finish_reason": "stop", "index": 0}]},
]

# Tool call response
MOCK_TOOL_CALL_RESPONSE = {
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_mock_123",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": '{"query": "latest news AI 2026"}',
                },
            }],
        },
        "finish_reason": "tool_calls",
    }],
}

# Error responses
MOCK_RATE_LIMIT_ERROR = {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}}
MOCK_AUTH_ERROR = {"error": {"message": "Incorrect API key", "type": "authentication_error"}}
MOCK_TIMEOUT_ERROR = TimeoutError("LLM request timed out after 30s")
MOCK_SERVER_ERROR = {"error": {"message": "Internal server error", "type": "server_error"}}


def get_mock_llm_provider(provider: str = "openai", stream: bool = False):
    """Return a configured mock for a specific LLM provider."""
    # Returns a mock object that simulates the provider's SDK
    ...
```

---

## 8. Test Data & Fixtures

### 8.1 Factory Functions (Backend)

**`backend/tests/factory.py`:**

```python
"""Factory functions for creating test data."""

from uuid import UUID, uuid4
from datetime import datetime, timezone
from app.core.auth import hash_password


def create_user_payload(
    email: str = "test@example.com",
    password: str = "TestPass123!",
    display_name: str = "Test User",
) -> dict:
    return {
        "email": email,
        "password": password,
        "display_name": display_name,
    }


def create_user_row(
    user_id: UUID | None = None,
    email: str = "test@example.com",
    display_name: str = "Test User",
    hashed: bool = True,
) -> dict:
    return {
        "id": user_id or uuid4(),
        "email": email,
        "password_hash": hash_password("TestPass123!") if hashed else "not-a-hash",
        "display_name": display_name,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }


def create_conversation_payload(
    title: str = "New Conversation",
) -> dict:
    return {"title": title}


def create_conversation_row(
    conversation_id: UUID | None = None,
    user_id: UUID | None = None,
    title: str = "Test Conversation",
) -> dict:
    return {
        "id": conversation_id or uuid4(),
        "user_id": user_id or uuid4(),
        "title": title,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }


def create_message_row(
    message_id: UUID | None = None,
    conversation_id: UUID | None = None,
    role: str = "user",
    content: str = "Hello",
) -> dict:
    return {
        "id": message_id or uuid4(),
        "conversation_id": conversation_id or uuid4(),
        "role": role,
        "content": content,
        "metadata_": None,
        "created_at": datetime.now(timezone.utc),
    }
```

### 8.2 Sample Conversation Scenarios

**`backend/tests/fixtures/conversations.py`:**

```python
"""Sample conversation scenarios for testing."""

SAMPLE_CONVERSATIONS = {
    "simple_qa": {
        "title": "Simple Q&A",
        "messages": [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."},
        ],
    },
    "multi_turn": {
        "title": "Multi-turn conversation",
        "messages": [
            {"role": "user", "content": "What's the weather like today?"},
            {"role": "assistant", "content": "I don't have real-time weather data, but I can help you search for it. Would you like me to look it up?"},
            {"role": "user", "content": "Yes, please search for 'London weather today'"},
            {"role": "assistant", "content": "I'll search for that now.", "tool_calls": [{"name": "web_search", "arguments": {"query": "London weather today"}}]},
            {"role": "tool", "content": "London: 15°C, partly cloudy", "tool_call_id": "call_123"},
            {"role": "assistant", "content": "Based on the search results, London currently has a temperature of 15°C with partly cloudy conditions."},
        ],
    },
    "code_generation": {
        "title": "Code generation",
        "messages": [
            {"role": "user", "content": "Write a Python function to reverse a linked list"},
            {"role": "assistant", "content": "```python\ndef reverse_linked_list(head):\n    prev = None\n    current = head\n    while current:\n        next_node = current.next\n        current.next = prev\n        prev = current\n        current = next_node\n    return prev\n```"},
        ],
    },
    "long_context": {
        "title": "Long context test",
        "messages": [
            {"role": "user", "content": "Tell me about " + "A" * 10000},
            {"role": "assistant", "content": "That's a lot of As! " + "B" * 1000},
        ],
    },
    "empty_conversation": {
        "title": "Empty conversation",
        "messages": [],
    },
}
```

### 8.3 Mock LLM Responses

```python
"""Predefined mock LLM responses for common test patterns."""

# Response types for different test scenarios
MOCK_RESPONSES = {
    "greeting": "Hello! I'm Jarvis, your AI assistant. How can I help you today?",
    "short_answer": "The answer is 42.",
    "long_answer": "Lorem ipsum dolor sit amet, " * 200,
    "code_block": "```python\nprint('hello world')\n```",
    "tool_call": None,  # Triggers tool execution middleware
    "error_gateway": "I'm sorry, I encountered an error processing your request.",
    "multi_language": "Bonjour! ¿Cómo estás? 你好!",
    "injection_attempt": "I cannot execute that request as it appears to be a prompt injection attempt.",
}
```

### 8.4 Test Database Seeding

```python
"""Database seeding scripts for tests."""

async def seed_test_data(db_session, num_users=3, conversations_per_user=2):
    """Seed the test database with realistic test data."""
    users = []
    for i in range(num_users):
        user = User(
            email=f"testuser{i}@example.com",
            password_hash=hash_password("TestPass123!"),
            display_name=f"Test User {i}",
        )
        db_session.add(user)
        users.append(user)
    
    await db_session.flush()
    
    conversations = []
    for user in users:
        for j in range(conversations_per_user):
            conv = Conversation(
                user_id=user.id,
                title=f"Conversation {j}",
            )
            db_session.add(conv)
            conversations.append(conv)
    
    await db_session.flush()
    
    for conv in conversations:
        msg = Message(
            conversation_id=conv.id,
            role="user",
            content="Hello, this is a test message.",
        )
        db_session.add(msg)
    
    await db_session.commit()
    return users, conversations
```

---

## 9. CI/CD Integration

### 9.1 Branch Protection Rules

| Branch | Required Checks | Approvals |
|--------|----------------|-----------|
| `main` | Lint, Backend Tests, Frontend Tests, E2E Tests | 2 |
| `develop` | Lint, Backend Tests, Frontend Tests, E2E Tests | 1 |
| `feat/*` | Lint, Backend Tests (quick), Frontend Tests (quick) | 0 (auto-merge blocked) |
| `fix/*` | Lint, Backend Tests (quick), Frontend Tests (quick) | 0 |

### 9.2 CI Optimization

| Strategy | Implementation |
|----------|---------------|
| **Test splitting** | Backend tests split into: `fast` (SQLite, <1min), `integration` (PostgreSQL, <3min), `slow` (voice/performance, <10min) |
| **Caching** | pip cache, npm cache, Playwright browsers cached |
| **Parallelism** | Frontend/Backend/E2E run in parallel |
| **Selective testing** | Only test changed packages (affected module detection) |
| **Flaky test management** | Auto-retry (2x), quarantine after 3 failures, Slack notification |

### 9.3 Test Results Reporting

- Coverage reports uploaded to Codecov / Coveralls
- Test failure notifications in PR comments
- Slack webhook for CI failures on `main`/`develop`
- Historical trend tracking for test duration and flakiness

---

## 10. Phase-by-Phase Rollout

### Phase 1: Foundation (Week 1-2)

| Task | Owner | Priority |
|------|-------|----------|
| Write pytest config + conftest.py | QA | P0 |
| Write unit tests for `core/auth.py` | QA | P0 |
| Write unit tests for database models | Backend | P1 |
| Set up Vitest + RTL for frontend | QA + Frontend | P0 |
| Write store tests (`auth.ts`) | QA | P0 |
| Set up pre-commit hooks | Lead | P0 |
| Create factory functions + fixtures | QA | P1 |

### Phase 2: API & Services (Week 2-4)

| Task | Owner | Priority |
|------|-------|----------|
| Write API endpoint tests (auth) | QA + Backend | P0 |
| Write WebSocket chat tests | QA | P0 |
| Write LLM service tests (mocked) | QA + Backend | P0 |
| Write rate limiting tests | QA | P1 |
| Write frontend component tests | QA + Frontend | P1 |
| Set up CI pipeline | Lead | P0 |

### Phase 3: Voice, Tools & E2E (Week 4-6)

| Task | Owner | Priority |
|------|-------|----------|
| Write voice service tests | QA + Backend | P1 |
| Write tool execution tests | QA + Backend | P1 |
| Write E2E tests (Playwright) | QA + Frontend | P0 |
| Write security penetration tests | QA | P1 |
| Set up Playwright with Electron | QA | P1 |
| Accessibility audit | QA | P2 |

### Phase 4: Performance & Polish (Week 6-8)

| Task | Owner | Priority |
|------|-------|----------|
| Write performance benchmarks | QA + Backend | P1 |
| Memory/CPU profiling | QA + Lead | P2 |
| Accent diversity testing | QA | P2 |
| Flaky test review and stabilization | QA | P1 |
| Test documentation | QA | P2 |

---

## Appendix A: Test Execution Commands

```bash
# Backend
cd backend
pytest                                                     # Run all backend tests
pytest tests/test_core/ -v                                 # Run auth/core tests
pytest tests/test_api/ -v -k "auth"                        # Run auth API tests
pytest tests/ -v --cov=app --cov-report=html               # Run with coverage report
pytest tests/ -v -m "not slow"                             # Run only fast tests
pytest tests/ -v --pdb                                     # Run with debugger on failure

# Frontend
cd frontend
npx vitest run                                             # Run all unit tests
npx vitest run --changed                                   # Run tests for changed files
npx vitest run --coverage                                  # Run with coverage
npx playwright test                                        # Run E2E tests
npx playwright test --debug                                # Run E2E with Playwright Inspector
npx playwright show-report                                 # View E2E results

# CI simulation
act pull_request                                           # Run GH Actions locally
```

## Appendix B: Key Files & Locations

| File | Purpose |
|------|---------|
| `backend/tests/conftest.py` | Global pytest fixtures (DB, auth, client) |
| `backend/tests/factory.py` | Test data factory functions |
| `backend/tests/fixtures/llm_responses.py` | Mock LLM response data |
| `backend/tests/fixtures/conversations.py` | Sample conversation scenarios |
| `frontend/tests/setup.ts` | Vitest global setup |
| `frontend/tests/unit/stores/auth.test.ts` | Auth store tests |
| `frontend/playwright.config.ts` | Playwright E2E configuration |
| `frontend/vitest.config.ts` | Vitest configuration |
| `.github/workflows/test.yml` | CI pipeline |
| `.pre-commit-config.yaml` | Pre-commit hook configuration |