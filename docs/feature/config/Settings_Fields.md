# Settings Configuration Fields

## 1. Synopsis

- **Purpose**: Application-level settings for server, CORS, and WebSocket
- **I/O**: YAML (`main.yml`) → `Settings` Pydantic model

## 2. Core Logic

### Server Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `host` | str | `"127.0.0.1"` | Server host address |
| `port` | int | `8000` | Server port (1-65535) |
| `cors_origins` | List[str] | `["*"]` | Allowed CORS origins |
| `app_name` | str | `"DesktopMate+ Backend"` | Application name |
| `app_version` | str | `"0.1.0"` | Application version |
| `debug` | bool | `False` | Enable debug mode |
| `health_check_timeout` | int | `5` | Health check timeout (seconds) |

### WebSocket Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_error_tolerance` | int | `5` | Max consecutive errors before close |
| `error_backoff_seconds` | float | `0.5` | Wait after transient errors |
| `inactivity_timeout_seconds` | int | `300` | Inactivity timeout (seconds) |

## 3. Usage

```yaml
# yaml_files/main.yml
settings:
  host: "0.0.0.0"
  port: 5500
  cors_origins:
    - "http://localhost:3000"
    - "https://myapp.com"
  debug: false
  health_check_timeout: 5
  websocket:
    max_error_tolerance: 5
    error_backoff_seconds: 0.5
    inactivity_timeout_seconds: 300
```

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
