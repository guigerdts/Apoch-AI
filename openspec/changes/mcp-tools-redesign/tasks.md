# Tasks: Rediseño de la API Pública MCP de Apoch-AI

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Low

## Políticas del Backlog

### Presupuesto por PR
| Límite | Valor |
|--------|-------|
| LOC netas | ≤400 |
| Archivos modificados | ≤15 |
| Capabilities nuevas | ≤1 |
| ADRs modificados | ≤1 |
| Refactors oportunistas | ❌ Prohibido |
| Deuda técnica nueva | ❌ Prohibido |

### Regla "No Feature Creep"
Durante cualquier PR está prohibido:
- Cambiar nombres no relacionados con el PR
- Mejorar arquitectura fuera del alcance
- Optimizar código no relacionado
- Refactorizar módulos existentes
- Agregar nuevas tools o capabilities
- Solo se implementa EXACTAMENTE lo aprobado por Spec + Design + Tasks

| Unit | Goal | PR | Test cmd | Rollback |
|------|------|----|----------|----------|
| 1A | Dominio: models, registry, errors, version, metrics | PR1A | `pytest tests/public_api/test_models.py tests/public_api/test_registry.py -v` | Revert `src/apoch/public_api/models.py registry.py errors.py version.py metrics.py` |
| 1B | Orquestación: Coordinator, Manager wiring (sin tools registradas) | PR1B | `pytest tests/public_api/test_coordinator.py tests/public_api/test_wiring.py -v` | Revert `src/apoch/public_api/coordinator.py` + Manager changes |
| 2 | apoch_status end-to-end | PR2 | `pytest tests/public_api/test_status.py -v` | Revert status + tests |
| 3 | apoch_health end-to-end | PR3 | `pytest tests/public_api/test_health.py -v` | Revert health + tests |
| 4 | apoch_history end-to-end | PR4 | `pytest tests/public_api/test_history.py -v` | Revert history + tests |
| 5 | apoch_recommend end-to-end | PR5 | `pytest tests/public_api/test_recommend.py -v` | Revert recommend + tests |
| 6 | apoch_progress end-to-end | PR6 | `pytest tests/public_api/test_progress.py -v` | Revert progress + tests |
| 7 | apoch_insights end-to-end | PR7 | `pytest tests/public_api/test_insights.py -v` | Revert insights + tests |
| 8 | apoch_logs end-to-end | PR8 | `pytest tests/public_api/test_logs.py -v` | Revert logs + tests |
| 9 | Legacy aliases + module cleanup | PR9 | `pytest tests/public_api/test_backward_compat.py -v` | Revert aliases + module get_tool_defs |
| 10 | Docs + benchmarks | PR10 | `pytest tests/ --benchmark-only` | Revert docs/ + benchmarks |

---

## Gate PR1 (antes de PR2)

PR1A + PR1B deben pasar esta validación antes de abrir PR2:

- [ ] Ruff: `ruff check src/apoch/`
- [ ] Pytest: `pytest tests/ -v`
- [ ] Tipado: `mypy src/apoch/`
- [ ] MCP inicia sin errores
- [ ] Coordinator instancia correctamente
- [ ] ServiceRegistry resuelve todos los servicios
- [ ] ToolResponse serializa a dict completo
- [ ] `api_version` en respuesta = "1.0"
- [ ] Ninguna tool nueva visible aún en MCP
- [ ] Ninguna tool legacy rota (alias no registrados todavía)

**Si falla cualquiera**: no avanzar a PR2 hasta corregir.

---

## PR 1A: Dominio Público

- [x] 1A.1 Crear `models.py` (ToolResponse, EvidenceSource, RecommendResponse, ErrorResponse) con dataclasses. Tests de serialización + validación + Go/No-Go.
- [x] 1A.2 Crear `registry.py` (ServiceRegistry tipado). Tests de construcción + validación + Go/No-Go.
- [x] 1A.3 Crear `version.py` (API_VERSION = "1.0"). Test de lectura + Go/No-Go.
- [x] 1A.4 Crear `errors.py` (catálogo global: ERR_TIMEOUT, ERR_NO_DATA, etc.). Tests de cada código + Go/No-Go.
- [x] 1A.5 Crear `metrics.py` (CallMetrics). Tests de estructura + Go/No-Go.

Sin Coordinator todavía. Sin registro MCP. Sin tools visibles.

---

## PR 1B: Orquestación (sin tools registradas)

- [x] 1B.1 Crear `coordinator.py` base con `_query_modules()` (timeouts, asyncio.gather, return_exceptions, degradación). Tests de resiliencia (1/N timeout, todos timeout) + validación + Go/No-Go.
- [x] 1B.2 Modificar `AgentAdapterManager` para construir ServiceRegistry e inyectar Coordinator. Sin registro de tools nuevas (registro progresivo: cada PR registra la suya). Tests de wiring + integración + Go/No-Go.
- [x] 1B.3 Pasar **Gate PR1** completo antes de abrir PR2.

---

## PR 2: apoch_status (Public Stable)

- [x] 2.1 Registrar `apoch_status` en MCP + implementar `ApochCoordinator.status()` orquestando Vision, Guardian, Chronicle, Oracle. Tests (happy, timeout, sin datos, problemas) + validación MCP + Go/No-Go.
- [x] 2.2 **Acceptance Gate**: tool visible en tools/list, ninguna tool futura visible, ninguna devuelve ERR_NOT_IMPLEMENTED.

## PR 3: apoch_health (Public Stable)

- [x] 3.1 Registrar `apoch_health` en MCP + implementar `ApochCoordinator.health()` con clasificación 🟢/🟡/🔴. Tests (sin problemas, advertencia, crítico, Guardian no disponible) + validación + Go/No-Go.
- [x] 3.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 4: apoch_history (Public Stable)

- [ ] 4.1 Registrar `apoch_history` en MCP + implementar `ApochCoordinator.history()` con filtros horas/tipo. Tests (happy, filtros, sin datos) + validación + Go/No-Go.
- [ ] 4.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 5: apoch_recommend (Public Stable)

- [ ] 5.1 Registrar `apoch_recommend` en MCP + implementar `ApochCoordinator.recommend()` orquestando Oracle, Optimizer, Pulse, Guardian, Vision. Tests (recomendación, sin datos, Oracle no disponible) + validación + Go/No-Go.
- [ ] 5.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 6: apoch_progress (Experimental)

- [ ] 6.1 Registrar `apoch_progress` en MCP + implementar `ApochCoordinator.progress()` con filtro periodo. Tests (datos, sin datos, tendencia) + validación + Go/No-Go.
- [ ] 6.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 7: apoch_insights (Experimental)

- [ ] 7.1 Registrar `apoch_insights` en MCP + implementar `ApochCoordinator.insights()` orquestando Optimizer, Pulse. Tests (oportunidades, sin datos, Optimizer no disponible) + validación + Go/No-Go.
- [ ] 7.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 8: apoch_logs (Advanced)

- [ ] 8.1 Registrar `apoch_logs` en MCP + implementar `ApochCoordinator.logs()` con filtros nivel/límite/módulo. Tests (filtros, sin resultados, límite) + validación + Go/No-Go.
- [ ] 8.2 **Acceptance Gate**: tool visible, futuras no, ninguna ERR_NOT_IMPLEMENTED.

## PR 9: Backward Compatibility

- [ ] 9.1 Registrar aliases legacy (vision_state→apoch_status, chronicle_query→apoch_history, guardian_diagnostics→apoch_health, guardian_all_diagnostics→apoch_health, vision_logs→apoch_logs) con metadata de deprecación.
- [ ] 9.2 Eliminar `get_tool_defs()` de módulos Vision, Chronicle, Guardian. Tests de alias + compatibilidad + Go/No-Go.

## PR 10: Documentación y Benchmarks

- [ ] 10.1 Documentar API completa (`docs/mcp-public-api.md`): propósito, contratos, ejemplos, migración.
- [ ] 10.2 Benchmarks de latencia por tool (p50, p95, p99). Limpieza final de código temporario.

---

## Fase Post-PR10: Acceptance

No es desarrollo. Es usar Apoch-AI en escenarios reales durante varios días.

- [ ] Instalar desde cero
- [ ] Conectar a OpenCode
- [ ] Resolver tareas reales usando únicamente tools públicas
- [ ] Medir utilidad y registrar fricciones
- [ ] Validar tiempos de respuesta
- [ ] Medir confianza de respuestas
- [ ] Confirmar que las tools Experimentales aportan valor

### Criterios Go/No-Go a v1.0.0

| Criterio | Mínimo |
|----------|--------|
| Tareas reales completadas con tools públicas | ≥5 |
| Fricciones críticas reportadas | 0 |
| Confianza media en respuestas | ≥ MEDIUM |
| Tools Experimentales confirman valor | ≥1 de 2 |

Solo después:

```
Tasks → Apply → PR merge → Acceptance → RC1 → RC2 (si aplica) → v1.0.0
```
