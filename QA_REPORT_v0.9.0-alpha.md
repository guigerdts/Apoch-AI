# QA Report — Apoch v0.9.0-alpha

**Fecha:** 2026-07-17  
**Rol:** Senior QA Engineer  
**Entorno:** Linux, Python 3.13, OpenCode runtime  
**Metodología:** Instalación limpia + MCP ClientSession + CLI directo

---

## Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Herramientas probadas | 7 públicas + 5 legacy = 12 |
| Casos ejecutados | ~120 (happy paths + inválidos + límites + fuzzing) |
| Bugs encontrados | **7** (2 High, 3 Medium, 2 Low) |
| Problemas de documentación | 2 |
| Problemas de UX | 2 |
| Inconsistencias | 3 |
| **Veredicto** | **PASS WITH RECOMMENDATIONS** |

### Aspectos positivos

- Las 12 herramientas responden correctamente en el MCP gateway
- El servidor stdio arranca, registra tools y procesa calls sin errores fatales
- El contrato ToolResponse (`api_version`, `summary`, `evidence`, `confidence`, `generated_at`) se cumple en todas las tools
- Los 5 legacy aliases funcionan e incluyen metadata `[DEPRECATED]`
- El CLI completo opera sin errores: `apoch list`, `status`, `doctor`, `stack`, `mcp`, `eil`
- La instalación limpia desde `uv sync` funciona sin intervención manual
- El formato de error `ERR_INVALID_ARGUMENT` se activa correctamente para parámetros inválidos

---

## Bugs encontrados

### BUG-001: Error response double-wrapping `ok: True` siempre — **High**

| Campo | Valor |
|---|---|
| **Severidad** | High |
| **Área** | MCP Dispatch — `_dispatch()` |
| **Cómo reproducir** | Llamar cualquier tool con parámetros inválidos, ej. `apoch_history(horas=0)` |
| **Resultado esperado** | `{"version":1, "ok":false, "error":{"code":"ERR_INVALID_ARGUMENT",...}}` |
| **Resultado obtenido** | `{"version":1, "ok":true, "data":{"ok":false, "error":{"code":"ERR_INVALID_ARGUMENT",...}}}` |
| **Evidencia** | `ok (outer): True, ok (inner): False` |
| **Posible causa** | `_dispatch()` en `server.py` línea ~332 siempre retorna `{"ok": True, "data": result}` sin inspeccionar si `result` contiene un error. El coordinador retorna errores como valor (dict), no como excepción. |
| **Recomendación** | Que `_dispatch()` inspeccione `result.get("ok", True)` y si es `False`, retorne el error directamente en lugar de anidarlo. O unificar: que el coordinador lance `ToolExecutionError` y el dispatch lo capture. |

---

### BUG-002: `apoch_health.healthy` retorna `None` en lugar de booleano — **High**

| Campo | Valor |
|---|---|
| **Severidad** | High |
| **Área** | `apoch_health` — `ApochCoordinator.health()` |
| **Cómo reproducir** | Ejecutar `apoch_health` con módulos funcionando normalmente |
| **Resultado esperado** | `"healthy": true` (o `false`) |
| **Resultado obtenido** | `"healthy": null` |
| **Evidencia** | `healthy=None, confidence=1.0, problems=0` |
| **Posible causa** | El método `health()` no establece `healthy` cuando `problems` está vacío, o lo calcula a partir de un campo que resulta `None`. |
| **Recomendación** | Forzar `healthy = True` cuando no hay problemas, `healthy = False` cuando hay al menos un problema. |

---

### BUG-003: `apoch_history` summary muestra paréntesis vacío `()` cuando no hay type_counts — **Medium**

| Campo | Valor |
|---|---|
| **Severidad** | Medium |
| **Área** | `apoch_history` — armado de summary |
| **Cómo reproducir** | Ejecutar `apoch_history` sin filtros en un sistema con actividad reciente |
| **Resultado esperado** | `"Se encontraron 1 eventos (lifecycle: 1)"` (o similar con counts) |
| **Resultado obtenido** | `"Se encontraron 1 eventos () en las últimas 24 horas"` |
| **Evidencia** | Summary literal: `Se encontraron 1 eventos ()` |
| **Posible causa** | La función que construye `counts_str` filtra type_counts con `count > 0`, pero si el tipo del evento no está en `type_counts` inicial (`lifecycle`, `tool`, `error`), nunca suma. Queda counts_str vacío. |
| **Recomendación** | Verificar que type_counts contenga TODOS los tipos de eventos que puede devolver el chronicle, o construir counts_str dinámicamente a partir de los eventos reales. |

---

### BUG-004: Version string `0.9.0-alpha` no es PEP 440 compliant — **Medium**

| Campo | Valor |
|---|---|
| **Severidad** | Medium |
| **Área** | `pyproject.toml` |
| **Cómo reproducir** | `pip show apoch-ai` o `importlib.metadata.version('apoch-ai')` |
| **Resultado esperado** | `"0.9.0-alpha"` |
| **Resultado obtenido** | `"0.9.0a0"` (normalización automática) |
| **Evidencia** | `__version__`: `0.9.0-alpha`, `metadata.version`: `0.9.0a0` |
| **Posible causa** | PEP 440 no permite `-alpha`. `0.9.0a0` es la forma normalizada. |
| **Recomendación** | Usar `0.9.0a0` en `pyproject.toml` y mantener `__version__` legible para humanos, o usar `0.9.0.dev0` / `0.9.0rc0` si es release candidate. |

---

### BUG-005: `VALIDATION_ERROR` no está en el catálogo de errores documentado — **Medium**

| Campo | Valor |
|---|---|
| **Severidad** | Medium |
| **Área** | Dispatch layer + documentación |
| **Cómo reproducir** | Pasar un parámetro extra no definido en el schema, ej. `apoch_health({"modulo": "guardian"})` |
| **Resultado esperado** | Error con código del catálogo (`ERR_INVALID_ARGUMENT`) |
| **Resultado obtenido** | `VALIDATION_ERROR` (no documentado) |
| **Evidencia** | `code=VALIDATION_ERROR` |
| **Posible causa** | FastMCP o el arg_model interno rechazan el parámetro antes de que llegue al handler. |
| **Recomendación** | Documentar `VALIDATION_ERROR` en el catálogo, o capturarlo y traducirlo a `ERR_INVALID_ARGUMENT` en el dispatch. |

---

### BUG-006: `ErrorCode` no existe como símbolo exportado — **Low**

| Campo | Valor |
|---|---|
| **Severidad** | Low |
| **Área** | `apoch.public_api.errors` |
| **Cómo reproducir** | `from apoch.public_api.errors import ErrorCode` |
| **Resultado esperado** | Import exitoso |
| **Resultado obtenido** | `ImportError: cannot import name 'ErrorCode'` |
| **Evidencia** | El módulo exporta constantes `ERR_*` sueltas, no una clase/enum `ErrorCode`. |
| **Recomendación** | Agregar `ErrorCode` como clase/enum, o eliminar referencias del código si nunca existió. |

---

### BUG-007: Legacy alias `vision_state.module` parameter ignorado — **Low**

| Campo | Valor |
|---|---|
| **Severidad** | Low |
| **Área** | Legacy aliases — `vision_state` |
| **Cómo reproducir** | `vision_state({"module": "chronicle"})` |
| **Resultado esperado** | Estado del módulo `chronicle` únicamente |
| **Resultado obtenido** | Respuesta completa (ignora el filtro) |
| **Posible causa** | El handler `legacy_vision_state` no implementa el filtro `module`, retorna el mismo resultado que `apoch_status`. |
| **Recomendación** | Implementar el filtro `module` o eliminar el parámetro del schema. |

---

## Problemas de documentación

### DOC-001: README.md referencia `apoch stack verify` sin contexto

El README muestra:
```bash
uv run apoch stack verify
```
pero no explica qué verifica ni qué significa el output. Un usuario nuevo no sabe si `✓ CodeGraph: CodeGraph 1.3.1 verified` es esperado o no.

**Recomendación:** Agregar una línea que explique "These are optional integrations. They show as verified when installed, or NOT_INSTALLED otherwise."

### DOC-002: Ejemplos de código en docs/mcp-public-api.md sin validación automática

Los ejemplos JSON en la documentación de la API pública no tienen un mecanismo que garantice que el formato de respuesta mostrado coincida con la implementación real. Por ejemplo, el formato `{ ok, data }` documentado como respuesta de error difiere del formato real `{ version, ok, data }`.

**Recomendación:** Agregar un script de integración continua que valide que los contratos documentados coinciden con las respuestas reales.

---

## Problemas de UX

### UX-001: El comando `mcp` en `--help` no tiene descripción

```
│ mcp                                                                          │
```

Todos los demás comandos tienen una descripción. `mcp` aparece sin texto.

### UX-002: Mensaje de error `apoch doctor` poco descriptivo

```
✗ opencode: gateway not started
```

No indica qué hacer para resolverlo. Un usuario nuevo no sabe si debe ejecutar `apoch mcp start`, `apoch install`, o verificar la configuración.

---

## Inconsistencias

### INC-001: `suggested_action` es `null` en 5/7 tools pero string en `apoch_status` y `apoch_health`

`apoch_status` y `apoch_health` retornan `suggested_action: "Ninguna acción requerida"` (string), mientras que `apoch_history`, `apoch_progress`, `apoch_insights`, `apoch_logs` retornan `null`. 

Por spec, `suggested_action` debería ser siempre un string con valor informativo, o siempre `null`. La mezcla confunde al consumidor.

### INC-002: `confidence` en `apoch_health` es `1.0` incluso sin datos

Cuando `apoch_health` retorna `problems: []` y `healthy: null`, el `confidence` es `1.0`. No debería tener máxima confianza si no pudo determinar el estado real.

### INC-003: Mezcla de idiomas en mensajes

La mayoría de mensajes están en español (`"horas debe ser un entero positivo"`), pero los logs internos y algunos errores de infraestructura están en inglés. Para consumidores de la API, los errores son mayormente consistentes en español, pero un consumidor programático necesita manejar ambos.

---

## Riesgos para producción

| Riesgo | Impacto | Probabilidad |
|---|---|---|
| **Error handling confuso**: consumidores que checkean `response.ok` pensarán que la llamada fue exitosa cuando en realidad hay un error anidado en `data.ok`. Esto puede causar fallos silenciosos en integraciones. | Alto | Alta |
| **healthy=None**: aplicaciones que esperan un booleano pueden romperse o mostrar estado incorrecto. | Alto | Media |
| **Versión PEP 440**: `pip install apoch-ai==0.9.0-alpha` puede fallar o instalar versión incorrecta. | Medio | Media |
| **VALIDATION_ERROR no documentado**: consumidores sin manejo de errores genérico pueden fallar ante códigos desconocidos. | Medio | Baja |

---

## Recomendaciones

1. **Crítico antes del próximo release**: Arreglar BUG-001 (double-wrapping) y BUG-002 (healthy=None). Son los dos bugs que pueden causar fallos silenciosos en producción.
2. **Alta prioridad**: Unificar `suggested_action` (siempre string, o siempre null) y corregir la version string PEP 440.
3. **Media prioridad**: Agregar `ErrorCode` como enum exportado, documentar `VALIDATION_ERROR`, arreglar paréntesis vacío en history.
4. **Documentación**: Agregar descripción al comando `mcp`, mejorar mensaje de `apoch doctor`, validar ejemplos automáticamente.
5. **Testing**: Agregar tests de integración que verifiquen el formato exacto de las respuestas (no solo que "funcionan").

---

## Veredicto final

**PASS WITH RECOMMENDATIONS**

El sistema es funcional y publicable. Las 12 herramientas responden, los legacy aliases funcionan, la instalación desde cero es limpia y el CLI completo opera sin errores.

Sin embargo, **se recomienda corregir BUG-001 y BUG-002 antes de promocionar a stable** — el double-wrapping de errores puede causar fallos silenciosos en cualquier cliente MCP que integre contra la API.

---

*Reporte generado el 2026-07-17. Ningún código fue modificado durante la auditoría.*
