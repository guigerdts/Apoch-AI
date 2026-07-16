## Objetivo

Este PR estabiliza la integración entre Apoch-AI y OpenCode. No introduce nuevas funcionalidades — corrige los bloqueantes descubiertos durante la auditoría técnica y valida el funcionamiento completo del framework sobre OpenCode mediante MCP y el Core Stack.

## Cambios

| Archivo | Cambio |
|---------|--------|
| `src/apoch/stack/registry.py` | Fix: discover() key por descriptor.name, no ep.name |
| `src/apoch/adapters/opencode/server.py` | Add: serve() con run_stdio_async() para transporte persistente |
| `src/apoch/adapters/manager.py` | Add: serve() delegando al adapter |
| `src/apoch/cli/mcp.py` | Add: comando serve (long-lived, stdio) |
| `src/apoch/modules/chronicle/module.py` | Fix: wrapper handlers para dispatch MCP (record, query) |
| `src/apoch/modules/vision/module.py` | Fix: params name→module para coincidir con ToolDef |
| `src/apoch/adapters/opencode/config.py` | Fix: path, key mcp, trailing commas, JSONC parser |
| `src/apoch/stack/components/codegraph.py` | Add: componente versionado al repo |
| `tests/stack/components/test_codegraph.py` | Add: tests del componente CodeGraph |
| `.gitignore` | Add: Python project defaults |
| `README.md` | Update: 1156 tests, v0.7.0-alpha, CLI refs, módulos |
| `CHANGELOG.md` | Update: v0.8.0-alpha con todos los fixes |
| `tests/test_opencode_config.py` | Update: asserts para nuevo formato mcp |
| `tests/test_opencode_install.py` | Update: asserts para nuevo formato |
| `tests/test_integration_pr2.py` | Update: asserts para nuevo formato |

## Validación Funcional

### Core Stack
```
CodeGraph (integrations) — INSTALLED, v1.3.1 ✓
Context7  (integrations) — INSTALLED, v0.5.4  ✓
Engram    (integrations) — INSTALLED, v1.19.0 ✓
OpenSpec  (integrations) — INSTALLED, v1.5.0  ✓
apoch stack verify — 4/4 verificados ✓
```

### MCP — 11 herramientas registradas y funcionales
```
chronicle_record(params=[source, event_type, details])       ✓ persiste a SQLite
chronicle_query(params=[source, event_type, since, until, limit]) ✓ consulta eventos
chronicle_stats(params=[])                                     ✓ estadísticas
guardian_diagnostics(params=[module_name])                     ✓ diagnóstico
guardian_all_diagnostics(params=[])                            ✓ todos diagnóstico
guardian_clear_diagnostics(params=[module_name])               ✓ limpia diagnóstico
guardian_clear_all(params=[])                                  ✓ limpia todos
vision_state(params=[module])                                  ✓ estado módulo
vision_config(params=[module])                                 ✓ config módulo
vision_logs(params=[limit, level])                             ✓ logs recientes
vision_system(params=[])                                       ✓ info sistema
```

```
✓ MCP initialized — 11 tools registered
✓ chronicle_record: event persisted to SQLite
✓ vision_system: returns python_version, platform, pid, uptime, memory_rss_mb
```

### OpenCode Integration
```
apoch install plan:
  mcp:
    context7: preserved ✓
    engram:   preserved ✓
    apoch:    command=["apoch", "mcp", "serve"], type=local ✓
  mcpServers key NOT present ✓
apoch uninstall: rollback limpio ✓
Config file untouched: ~/.config/opencode/opencode.json intact ✓
```

### Testing
```
Ruff: All checks passed!
Tests: 1,156 total (1,105 unit + 51 e2e)
Passed: 1,148 (8 CI-only skip)
```

## Plan de revisión

1. Verificar que cada archivo modificado tenga sentido
2. Revisar que el parser JSONC no tenga falsos positivos con glob patterns
3. Confirmar que la integración OpenCode produce el formato correcto
4. Aprobar solo si la validación funcional es convincente
