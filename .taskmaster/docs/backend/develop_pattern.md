# Backend Structure
├── backend-api/              # 🐍 Python FastAPI Backend
│   ├── configs/              # ⚙️ Configuration Files
│   ├── src/                  # 📦 Python Source Code
│   │   ├── main.py           #    - FastAPI App & WebSocket Entry Point
│   │   ├── services/         #    - Business Logic (LLM, TTS.. ETC)
│   └── pyproject.toml        #    - Project Dependencies
└── README.md                 # 📄  Document

# Development Patterns

All Service should be follow "Simple as possible" principle.

1. All api server should be stateless.
2. All service should be independent.
3. All service should be testable.
4. All service should be using external api like openai, local vllm. Don't add any gpu server in the backend. Just use external api server for simplification.