# STM Configuration Fields

## 1. Synopsis

- **Purpose**: Configure MongoDB-based Short-Term Memory settings
- **I/O**: YAML → `MongoDBShortTermMemoryConfig` Pydantic model

## 2. Core Logic

### MongoDBShortTermMemoryConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `connection_string` | str | `"mongodb://admin:test@localhost:27017/"` | MongoDB URI |
| `database_name` | str | `"desktopmate_db"` | Database name |
| `sessions_collection_name` | str | `"sessions"` | Sessions collection |
| `messages_collection_name` | str | `"messages"` | Messages collection |
| `base_dir` | str | `"static/images"` | Image storage directory |

## 3. Usage

```yaml
# yaml_files/services/stm_service/mongodb.yml
stm_config:
  type: "mongodb"
  configs:
    connection_string: "mongodb://admin:password@localhost:27017/"
    database_name: "stm_db"
    sessions_collection_name: "sessions"
    messages_collection_name: "messages"
    base_dir: "static/images"
```

---

## Appendix

### A. Related Documents

- [Configuration System](./README.md)
- [STM Service](../service/STM_Service.md)
