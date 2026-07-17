# Proposal: Rediseño de la API Pública MCP de Apoch-AI

## Intent

La API MCP actual expone la arquitectura interna (vision_state, chronicle_record, guardian_diagnostics). El usuario necesita conocer Vision, Chronicle, Guardian, Pulse, Optimizer y Oracle para usar el sistema. Esto es incorrecto. La interfaz pública debe representar **intenciones humanas**, no módulos. Rediseñar completamente la superficie pública para que cualquier usuario —sin conocimiento de la arquitectura— pueda entender, descubrir y usar las herramientas en menos de 30 segundos.

## Scope

### In Scope
- Diseñar **nueva API pública MCP** desde preguntas humanas, agrupada por intención (no por módulo)
- **7 herramientas candidatas** (nombres por confirmar en Specification):
  - `apoch_status` — ¿Qué está pasando?
  - `apoch_history` — ¿Qué pasó?
  - `apoch_health` — ¿Tengo algún problema?
  - `apoch_recommend` — ¿Qué debería hacer ahora?
  - (candidato) `apoch_progress` — ¿Cómo voy?
  - (candidato) `apoch_insights` — ¿Cómo puedo mejorar?
  - (candidato) `apoch_logs` — Debug técnico
- **4 niveles de estabilidad**: Public Stable, Advanced, Internal, Experimental
- **Contratos de salida** por herramienta: propósito, cuándo usarla, qué nunca devuelve, formato, detalle, tiempo objetivo, dependencias internas
- **Principio de respuesta unificado**: resumen ejecutivo → explicación → evidencia → acción sugerida
- **Regla de separación**: tools públicas son consulta; acciones que mutan estado son excepcionales, explícitas y confirmables
- **Validación de usabilidad**: prueba con usuarios nuevos (4 preguntas por tool)
- **Diseño para crecimiento**: la API debe soportar 20+ herramientas sin perder coherencia
- Especificaciones SDD, ADRs, matriz de compatibilidad, plan de migración, validación UX

### Out of Scope
- Código, implementación o PRs
- Cambios en la arquitectura interna de módulos
- Eliminar o fusionar módulos
- Tools que dupliquen capacidades de OpenCode

## Capabilities

### New Capabilities
- `mcp-public-api`: Nueva API pública unificada basada en intención humana, con niveles de estabilidad y contratos de salida definidos
- `mcp-internal-services`: Capa de coordinación entre módulos que reemplaza las tools internas eliminadas

### Modified Capabilities
- `module-vision`: Deja de exponer tools directas; pasa a ser backend de `apoch_status` y `apoch_health`
- `module-chronicle`: Deja de exponer tools directas; pasa a ser backend de `apoch_history`
- `module-guardian`: Guardian_clear_* pasan a automáticas; diagnostics se consume via `apoch_health`
- `module-pulse`: Nuevo backend para progress (sin tools directas)
- `module-optimizer`: Nuevo backend para insights (sin tools directas)
- `module-oracle`: Nuevo backend para recommend (sin tools directas)

## UX Audit — Clasificación de Tools con Niveles de Estabilidad

| Tool actual | Estabilidad actual | Nueva estabilidad | Reemplazo |
|---|---|---|---|
| `vision_system` | Public | 🗑️ **Eliminar** | — |
| `vision_state` | Public | ✅ **Public Stable** | `apoch_status` |
| `vision_config` | Public | 🔒 **Internal** | — |
| `vision_logs` | Public | ⚡ **Advanced** | `apoch_logs` (candidato) |
| `chronicle_record` | Public | 🔒 **Internal** | — |
| `chronicle_query` | Public | ✅ **Public Stable** | `apoch_history` |
| `chronicle_stats` | Public | ⚡ **Advanced** | Absorbida en history como conteos contextuales por tipo. Sin tool independiente. Ver decisión B4. |
| `guardian_diagnostics` | Public | ✅ **Public Stable** | `apoch_health` |
| `guardian_all_diagnostics` | Public | ✅ **Public Stable** | (fusionado en health) |
| `guardian_clear_diagnostics` | Public | 🔄 **Internal** (auto) | — |
| `guardian_clear_all` | Public | 🔄 **Internal** (auto) | — |
| *(nuevo)* | — | ✅ **Public Stable** | `apoch_recommend` |
| *(nuevo)* | — | 🧪 **Experimental** | `apoch_progress` (candidato) |
| *(nuevo)* | — | 🧪 **Experimental** | `apoch_insights` (candidato) |

## Approach

1. **Evaluar nombres en Specification**: `apoch_progress`, `apoch_insights`, `apoch_logs` son candidatos — evaluar alternativas (consistencia, claridad, descubribilidad, alineación CLI) y justificar la elección final
2. Definir contratos de salida para cada herramienta (propósito, uso, qué no devuelve, formato, detalle, tiempo objetivo, dependencias internas)
3. Definir principio de respuesta unificado (resumen → explicación → evidencia → acción sugerida)
4. Establecer regla de separación: consulta vs acciones (acciones = excepcionales, explícitas, confirmables)
5. Diseñar para 20+ herramientas: nueva herramienta debe responder pregunta humana distinta y no duplicar capacidades
6. Diseñar capa de coordinación interna que reemplaza las tools eliminadas
7. Incorporar validación de usabilidad (4 preguntas por tool con usuarios nuevos)
8. Documentar ADRs por decisión de diseño
9. Plan de migración desde API actual (backward compat layer)
10. Estrategia de validación y criterios de aceptación verificables

## Principios Arquitectónicos

### Niveles de Estabilidad
| Nivel | Significado | Compatibilidad |
|---|---|---|
| **Public Stable** | Para usuarios finales | Compatibilidad hacia atrás garantizada |
| **Advanced** | Para usuarios avanzados y desarrolladores | Cambios posibles con aviso |
| **Internal** | No expuesta por MCP | Sin contrato público |
| **Experimental** | Futuras herramientas antes de estabilizar | Puede cambiar o desaparecer |

### Principio de Respuesta Unificado
Toda herramienta Public Stable y Advanced debe seguir este patrón:
1. **Resumen ejecutivo** — una línea con la respuesta principal
2. **Explicación breve** — contexto de la respuesta
3. **Evidencia** — datos o hechos que la respaldan
4. **Acción sugerida** — qué hacer con la información (si aplica)

### Separación Consulta / Acción
- Las herramientas públicas son **principalmente de consulta**
- Las acciones que modifican estado deben ser: **excepcionales**, **explícitas** en su nombre, y **confirmables**
- Toda acción debe poder revertirse

### Diseño para Crecimiento (20+)
Cada nueva herramienta debe:
- Responder una **pregunta humana distinta**
- **No duplicar** capacidades existentes
- Pasar los 7 criterios de aceptación
- Tener un nivel de estabilidad asignado

## Contratos de Salida (por definir en Specification)

Cada herramienta especificará:
| Campo | Descripción |
|---|---|
| **Propósito** | Pregunta humana que responde |
| **Cuándo usarla** | Escenario concreto |
| **Qué nunca devuelve** | Límites explícitos |
| **Formato de respuesta** | Estructura del output |
| **Nivel de detalle** | Terso / Normal / Detallado |
| **Tiempo objetivo** | Latencia máxima aceptable |
| **Dependencias internas** | Módulos que consulta (informativo, no visible al usuario) |

## Validación de Usabilidad

Cada herramienta debe validarse con usuarios nuevos mediante 4 preguntas:
1. ¿Entendiste para qué sirve? (sí / parcial / no)
2. ¿Supiste cuándo usarla? (sí / dudaste / no)
3. ¿La respuesta te ayudó? (sí / parcial / no)
4. ¿Necesitaste conocer módulos internos? (sí / no)

Si alguna respuesta es negativa, la herramienta vuelve a diseño.

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Breaking change para agentes que usan tools actuales | Media | Backward-compat alias layer; migración gradual |
| Nombres candidatos (progress/insights/logs) requieren revisión | Baja | Evaluación explícita en Specification con alternativas |
| `apoch_recommend` muy pesado al orquestar 5 módulos | Alta | Estrategia de módulos opt-in; timeout por módulo |
| Validación de usabilidad frena avance | Baja | Pruebas con 1-2 usuarios; iteración rápida |

## Rollback Plan

Revert los specs de la nueva API en git. Mantener la API actual funcionando durante la migración. La capa de compatibilidad permite rollback sin afectar agentes.

## Success Criteria

- [ ] 7 herramientas públicas candidatas con nivel de estabilidad asignado
- [ ] 3 nombres candidatos (progress/insights/logs) evaluados con alternativas y justificados
- [ ] Cada tool pasa los 7 criterios de aceptación + 4 preguntas de usabilidad
- [ ] Principio de respuesta unificado implementado en todas las tools Public Stable
- [ ] Regla consulta/acción documentada y aplicada
- [ ] Diseño preparado para 20+ herramientas (criterio de inclusión definido)
- [ ] Contratos de salida definidos por herramienta
- [ ] Una persona nueva entiende cada tool en ≤30s leyendo solo nombre + descripción
- [ ] La API actual sigue funcionando (backward compat layer)
- [ ] Todos los módulos internos siguen funcionando sin cambios en sus responsabilidades
- [ ] Matriz de compatibilidad documentada
- [ ] Plan de migración desde API actual documentado
