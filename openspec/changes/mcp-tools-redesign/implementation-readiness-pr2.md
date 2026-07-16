# Implementation Readiness Review: PR2 (apoch_status)

## Resumen Ejecutivo

**PR2 está READY para implementarse** después de una corrección obligatoria en PR1B.

El análisis confirma que la infraestructura actual (models, registry, coordinator engine, errors, manager wiring) soporta PR2 sin modificaciones arquitectónicas. Sin embargo, **manager.py aún registra las 7 tools públicamente** (herencia de Estrategia A), lo que contradice la nueva política de Registro Progresivo. PR1B debe corregirse antes de que PR2 pueda registrar `apoch_status` limpiamente.

---

## 1. Hallazgo Crítico: manager.py registra las 7 tools

### Problema

`src/apoch/adapters/manager.py` líneas 111-192 registra las 7 tools MCP públicas en `AgentAdapterManager.start()`:

```python
coordinator_tools: list[ToolDef] = [
    ToolDef(name="apoch_status", ...),
    ToolDef(name="apoch_history", ...),
    ToolDef(name="apoch_health", ...),
    ToolDef(name="apoch_recommend", ...),
    ToolDef(name="apoch_progress", ...),
    ToolDef(name="apoch_insights", ...),
    ToolDef(name="apoch_logs", ...),
]
await self._adapter.register_module_tools("coordinator", self._coordinator, coordinator_tools)
```

Esto contradice:
- **ADR-001** (actualizado): "El registro MCP ocurre únicamente cuando la implementación está completa y validada"
- **P10 — Public Visibility Rule**: "Una herramienta incompleta nunca debe ser descubrible por un cliente MCP"
- **Non-Goal #9** (design.md y spec.md): "No registrar herramientas incompletas"

### Solución Requerida

Eliminar las líneas 111-192 de `manager.py` (todo el bloque `coordinator_tools` y su registro). Mantener el Coordinator creado e inyectado, pero sin registrar herramientas. El archivo `coordinator.py` mantiene sus 7 stubs internos — no se eliminan, solo no se registran.

Cada PR (PR2–PR8) agregará su propio `ToolDef` y llamará `register_module_tools` para exactamente una herramienta.

**Esto debe hacerse ANTES de PR2.** Es un cambio pequeño y localizado en manager.py.

---

## 2. Verificación del Coordinator

**Estado: ✅ Ready para PR2**

| Verificación | Resultado |
|-------------|-----------|
| ¿Coordina en lugar de interpretar? | ✅ `_query_modules()` ejecuta, recolecta, agrega. No hay lógica de negocio. |
| ¿Sin imports de módulos concretos? | ✅ Solo importa `ServiceRegistry`, `EvidenceSource`, `error_response`, `API_VERSION`. |
| ¿Sin imports circulares? | ✅ No importa adapters, manager, ni módulos concretos. |
| ¿Timeouts configurables? | ✅ `DEFAULT_TIMEOUTS` como dict module-level. |
| ¿Errores del catálogo? | ✅ Usa `error_response()` de errors.py exclusivamente. |
| ¿ToolResponse como salida? | ✅ `_build_success_response()` produce dict compatible con ToolResponse. |

### Observaciones

- `_build_evidence()` usa confidence fijo `0.8` y `collected_ago=0`. PR2 debería reemplazar estos valores con datos reales de los módulos. **No blocking**, se mejora en PR2.
- `_build_success_response()` no recibe `results` con metadata temporal. PR2 debería pasar timestamps reales de los módulos. **No blocking**.

---

## 3. Contrato de apoch_status

### Especificación desde la Spec

| Aspecto | Valor |
|---------|-------|
| **Módulos** | Vision, Guardian, Chronicle, Oracle |
| **Entradas** | Ninguna |
| **Salida** | Summary, Explanation, Evidence, Suggested Action, Confidence, generated_at, data_freshness |
| **Contiene** | Estado general, componentes activos, problemas detectados, actividad reciente, recomendación rápida |
| **Sin datos** | "Sistema iniciado, sin actividad registrada" |
| **Confidence** | HIGH (es estado actual, no predicción) |
| **Tiempo objetivo** | < 2s |
| **Anti-patrones** | No mostrar PID, RAM, threads, objetos Python, rutas internas, nombres de clase, módulos |

### Contrato desde Design (ADR-001)

| Aspecto | Valor |
|---------|-------|
| **Módulos** | Vision, Guardian, Chronicle, Oracle |
| **Timeouts** | Vision(1s), Guardian(0.5s), Chronicle(0.5s), Oracle(2s) |
| **Fallo parcial** | Responde con datos disponibles, confidence baja |
| **Fallo total** | ERR_TIMEOUT |
| **Evidencia mínima** | 1+ source para respuesta completa. 0 sources → ERR_TIMEOUT. |

### ¿ToolResponse es suficiente?

**✅ Sí.** ToolResponse cubre todos los campos requeridos:

| Campo | apoch_status lo necesita | ¿ToolResponse lo tiene? |
|-------|------------------------|------------------------|
| `api_version` | ✅ | ✅ Siempre "1.0" |
| `summary` | ✅ "🟢/🟡/🔴" + estado | ✅ |
| `explanation` | ✅ Contexto breve | ✅ |
| `evidence` | ✅ Componentes activos, datos | ✅ |
| `suggested_action` | ✅ "Ninguna acción requerida" o recomendación | ✅ |
| `confidence` | ✅ HIGH normalmente | ✅ |
| `generated_at` | ✅ Timestamp | ✅ |
| `data_freshness` | ✅ Antigüedad de datos | ✅ |
| `metadata` | ✅ Reservado | ✅ |

**No sobran campos.** Todos son necesarios. No falta ninguno.

---

## 4. Registro MCP — Qué cambia exactamente en PR2

PR2 debe tocar **EXACTAMENTE** estos archivos (nada más):

| Archivo | Cambio | Líneas estimadas |
|---------|--------|-----------------|
| `manager.py` | Agregar ToolDef para `apoch_status` + `register_module_tools` | ~10 |
| `coordinator.py` | Implementar `status()` con lógica real (no stub) | ~40 |
| `tests/public_api/test_status.py` | Tests de status (happy, timeout, problemas, sin datos) | ~100 |
| `openspec/changes/mcp-tools-redesign/tasks.md` | Marcar 2.1 y 2.2 como `[x]` | 1 |
| `docs/mcp-public-api.md` | Documentar `apoch_status` | ~20 |

**Total estimado: ~170 líneas.** Dentro del presupuesto de ≤400 LOC.

### Lo que NO debe cambiar en PR2

- `models.py` — sin cambios
- `registry.py` — sin cambios
- `errors.py` — sin cambios
- `version.py` — sin cambios
- `metrics.py` — sin cambios
- `coordinator.py` — solo el método `status()`. Los otros 6 stubs se quedan igual.
- `manager.py` — solo agregar ToolDef de status. No tocar nada más.

---

## 5. Riesgos Identificados

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| **manager.py registra 7 tools** (hallazgo crítico) | 🔴 **Blocking** | Corregir PR1B antes de PR2 |
| Coordinator no recibe `data_freshness` real de módulos | 🟡 Medio | PR2 debe calcularlo desde timestamps de módulos |
| `_build_evidence()` usa confidence fijo 0.8 | 🟡 Medio | PR2 debe pasar confidence real de cada módulo |
| `_build_evidence()` usa `key.capitalize()` para source name | 🟢 Bajo | VisionModule → "Vision" funciona. Verificar que todos los módulos tengan nombres que capitalize() funcione bien. |
| Lógica de "estado general" podría requerir interpretación que pertenece a módulos | 🟡 Medio | La interpretación del estado (🟢/🟡/🔴) debe venir de Guardian, no calcularse en Coordinator. Validar en PR2. |

---

## 6. Checklist de Salida para PR2

### Gate Técnico

- [ ] Ruff: `ruff check src/apoch/`
- [ ] Pytest: `pytest tests/ -v`
- [ ] Cobertura: ≥80% en `src/apoch/public_api/`
- [ ] MCP inicia sin errores
- [ ] `tools/list` muestra `apoch_status`
- [ ] `apoch_status` devuelve respuesta válida
- [ ] Ninguna tool futura (`health`, `history`, `recommend`, etc.) aparece en `tools/list`
- [ ] Ninguna tool devuelve `ERR_NOT_IMPLEMENTED` (porque ninguna no-implementada está registrada)
- [ ] Tools legacy (`vision_state`, etc.) siguen funcionando sin cambios

### Gate Funcional (apoch_status específico)

- [ ] Summary incluye indicador 🟢/🟡/🔴
- [ ] Explanation tiene contexto breve
- [ ] Evidence lista componentes activos
- [ ] Suggested Action presente (aunque sea "Ninguna acción requerida")
- [ ] Confidence ≥ 0.75 (HIGH) en happy path
- [ ] `api_version = "1.0"`
- [ ] `generated_at` es ISO 8601 válido
- [ ] `data_freshness` es entero ≥ 0
- [ ] ToolResponse coincide con el formato de `models.py`
- [ ] No expone módulos internos (Vision, Guardian, etc.) como nombres en la respuesta
- [ ] No expone PID, RAM, threads, rutas, nombres de clase
- [ ] Sin datos → "Sistema iniciado, sin actividad registrada"

### Gate de Progreso

- [ ] `tasks.md` marca 2.1 y 2.2 como `[x]`
- [ ] `docs/mcp-public-api.md` documenta `apoch_status`
- [ ] Evidencia recopilada (Ruff, pytest, cobertura, diff --stat)
- [ ] Sin deuda técnica nueva
- [ ] Sin feature creep

---

## 7. ¿Puede PR2 ser la plantilla oficial para PR3–PR8?

**Sí, con una salvedad.**

### Por qué sí

1. **Arquitectura consistente:** Todos los PR siguen el mismo patrón:
   - ToolDef en manager.py → `register_module_tools` → implementar método en Coordinator → tests → Acceptance Gate
   - ServiceRegistry inyectado, Coordinator sin lógica de negocio, ToolResponse único formato

2. **Infraestructura compartida:** `_query_modules()`, `_build_evidence()`, `_calculate_confidence()`, `_build_success_response()` son reutilizables en todos los PR. No necesitan cambios.

3. **Misma estructura de tests:** Cada PR tendrá tests de happy path, timeout, sin datos, degradación. El patrón de testing es idéntico.

4. **Acceptance Gate uniforme:** Todos los PR2–PR8 verifican: tool visible, futuras no visibles, ninguna ERR_NOT_IMPLEMENTED.

### Salvedad

**PR5 (apoch_recommend)** es el más complejo (5 módulos, RecommendResponse con priority/expected_benefit, confidence variable). Puede requerir:
- Un `RecommendResponse` más completo si los datos de Oracle necesitan campos adicionales
- Lógica de priorización que debe venir de Oracle, no del Coordinator

Para mantener el patrón, PR5 debe:
- Usar `RecommendResponse` (ya existe en models.py)
- Delegar toda la priorización a Oracle
- No calcular priority en Coordinator

Si PR5 encuentra que RecommendResponse necesita más campos, se actualiza models.py en PR5, no antes.

### Checklist reusable

El siguiente template aplica a PR2–PR8:

```markdown
## Gate PR{N}
- [ ] Ruff
- [ ] Pytest
- [ ] Cobertura ≥80%
- [ ] Tool visible en tools/list
- [ ] Herramientas futuras NO visibles
- [ ] Ninguna ERR_NOT_IMPLEMENTED visible
- [ ] ToolResponse correcto
- [ ] Confidence correcto
- [ ] Tools legacy intactas
- [ ] Acceptance Gate: tool funcional + validada
- [ ] tasks.md actualizado
- [ ] docs/mcp-public-api.md actualizado
- [ ] Sin feature creep
- [ ] Evidencia recopilada
```

---

## Acción Inmediata Requerida

Antes de comenzar PR2, ejecutar:

**Fix PR1B:** Eliminar el bloque `coordinator_tools` (líneas 111-192) de `src/apoch/adapters/manager.py`. El Coordinator se crea e inyecta, pero no registra herramientas. Esto alinea el código con la documentación SDD actualizada.

Después de ese fix, PR2 puede proceder sin impedimentos.
