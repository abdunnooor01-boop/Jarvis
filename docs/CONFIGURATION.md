# Configuration — Local LLM Setup

## Overview

Jarvis supports multiple LLM providers. By default it uses OpenAI, but you can
switch to a fully local setup using Ollama.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai` | Provider to use: `openai` or `ollama` |
| `OPENAI_API_KEY` | — | OpenAI API key (required for `openai` provider) |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Ollama model name |

## Ollama Setup

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

### 2. Start Ollama

```bash
ollama serve
```

### 3. Pull a model

```bash
# Recommended: llama3 (7B) — runs well on 8GB+ RAM
ollama pull llama3

# For lower-resource devices: tinyllama or phi
ollama pull tinyllama
```

### 4. Configure Jarvis

Set the following environment variables:

```bash
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=llama3
```

Or add to your `.env` file:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### 5. Verify

When Jarvis starts, you should see:

```
Ollama provider registered  base_url=http://localhost:11434 model=llama3
```

If Ollama is not running, the provider will return a clear error message
indicating it's unreachable, and Jarvis will fall back gracefully.

## Switching Providers

You can switch providers at runtime by passing the `provider` parameter to
`LLMService.chat()` or `LLMService.stream_chat()`:

```python
from app.services.llm import get_llm_service

llm = get_llm_service()

# Use the default provider (configured via LLM_PROVIDER)
response = await llm.chat(messages)

# Use a specific provider
response = await llm.chat(messages, provider="ollama")
response = await llm.chat(messages, provider="openai")
```

## Listing Available Models

When using the Ollama provider, you can list available models:

```python
from app.services.llm import OllamaProvider

provider = OllamaProvider()
models = await provider.list_models()
for m in models:
    print(m["name"])
```