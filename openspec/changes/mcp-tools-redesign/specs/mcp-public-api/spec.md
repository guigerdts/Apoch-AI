# API Pública MCP — Especificación Completa v1.1

## Propósito

La API MCP de Apoch-AI pasa de estar organizada por módulos internos (Vision, Chronicle, Guardian) a organizarse por **intenciones humanas**. El usuario formula preguntas — el sistema orquesta los módulos necesarios.

## Principios de Diseño

### P1: Una herramienta = una intención humana
Nunca un módulo, clase, DB o implementación.

### P2: Formato de respuesta unificado
Toda herramienta Public Stable y Advanced sigue este contrato:
1. **Summary** — una línea con la respuesta principal
2. **Explanation** — contexto breve de la respuesta
3. **Evidence** — datos o hechos que la respaldan
4. **Suggested Action** — qué hacer con la información (si aplica)
5. **Confidence** — nivel de confianza (LOW / MEDIUM / HIGH o 0.00–1.00)

### P3: Freshness obligatoria
Toda respuesta incluye:
- `generated_at`: timestamp ISO 8601 de cuándo se generó
- `data_freshness`: antigüedad de los datos fuente en segundos

### P4: Separación consulta / acción
Las herramientas públicas son de consulta. Acciones que mutan estado son excepcionales, explícitas, confirmables y reversibles.

### P5: Una tool nunca depende de otra
Toda tool responde COMPLETAMENTE. Nunca deriva a otra tool. Solo puede mencionar "More details available in: apoch_health" como nota, nunca como requisito.

### P6: Una tool nunca expone su implementación
No muestra: módulos consultados, orden de ejecución, dependencias internas. Solo entrega la respuesta y la evidencia suficiente para justificarla.

### P7: Intent Stability Rule
La API pública es estable aunque cambie la implementación interna. Si mañana se reemplazan Oracle, Pulse, Chronicle, Vision o Guardian, las tools públicas (`apoch_status`, `apoch_history`, `apoch_health`, `apoch_recommend`) no cambian. La API depende de la intención del usuario, nunca de la arquitectura.

### P8: Regla de 30 segundos
Un usuario nuevo entiende qué hace, cuándo usarla y qué devuelve solo con nombre + descripción de una línea.

### P9: Independencia
Cada herramienta aporta valor por sí sola. Ninguna depende conceptualmente de otra.

### P10: Public Visibility Rule (Registro Progresivo)
Una capacidad interna puede existir antes que su contraparte pública. Las interfaces públicas (tools MCP) solo se registran cuando aportan valor completo al usuario. Una herramienta incompleta nunca debe ser descubrible por un cliente MCP. El registro forma parte del PR funcional correspondiente.

---

## Versionado de la API

La API pública MCP usa `api_version` como campo reservado en toda respuesta.

| Campo | Tipo | Valor actual | Contrato |
|-------|------|-------------|----------|
| `api_version` | string | `"1.0"` | Solo cambia con breaking changes. Versión MAJOR incrementa cuando se eliminan o modifican campos obligatorios. Versión MINOR incrementa con adiciones compatibles. |

`api_version` es el primer campo de toda respuesta. Permite que los clientes detecten automáticamente cambios en el contrato.

---

## Non-Goals

Esta especificación NO incluye ni incluirá en el futuro:

1. **Ejecutar acciones automáticamente.** Las tools públicas son de consulta. Nunca modifican estado del sistema.
2. **Modificar configuración.** No hay tools para cambiar config de Apoch-AI vía MCP.
3. **Escribir en Chronicle desde tools públicas.** `chronicle_record` es Internal — los agentes no escriben eventos directamente.
4. **Exponer módulos internos.** Ninguna tool pública revela Vision, Chronicle, Guardian, Pulse, Optimizer u Oracle.
5. **Depender del orden de ejecución interno.** La implementación puede cambiar el orden de consulta a módulos sin afectar la API.
6. **Mantener estado entre llamadas MCP.** Cada llamada es independiente. No hay sesiones, contexto ni memoización implícita.
7. **Romper compatibilidad en versiones Public Stable.** Toda tool Public Stable garantiza backward compatibility. Los cambios solo ocurren en Experimental y Advanced.
8. **Crear herramientas sin aprobar los 7 criterios de aceptación.** Ninguna tool nueva ingresa a la API sin pasar la acceptance matrix completa.
9. **Registrar herramientas incompletas.** Las tools MCP se registran únicamente cuando están totalmente implementadas y validadas. No existen stubs públicos. Ninguna tool pública devuelve ERR_NOT_IMPLEMENTED.

---

## Niveles de Confianza

Toda respuesta que incluye una evaluación (no un hecho objetivo) usa estos niveles:

| Rango | Etiqueta | Significado |
|-------|----------|-------------|
| 0.90–1.00 | Very High | Certeza casi absoluta. Datos suficientes y recientes. |
| 0.75–0.89 | High | Confianza sólida. Datos disponibles con alguna limitación menor. |
| 0.50–0.74 | Medium | Confianza moderada. Datos parciales o parcialmente desactualizados. |
| 0.25–0.49 | Low | Confianza baja. Pocos datos o fuente no disponible. |
| 0.00–0.24 | Very Low | Casi sin información. La respuesta es especulativa. |

Toda respuesta MUST incluir `confidence` como número (`0.00`–`1.00`). Las tools Public Stable DEBEN poder expresarlo también como etiqueta (LOW/MEDIUM/HIGH/VERY_HIGH).

---

## Catálogo Global de Códigos de Error

Todas las tools públicas usan EXCLUSIVAMENTE estos códigos. Nunca inventan nuevos.

| Código | Significado | Cuándo ocurre |
|--------|------------|---------------|
| `ERR_TIMEOUT` | La consulta excedió el tiempo máximo de espera | Módulo interno no responde a tiempo |
| `ERR_NO_DATA` | No hay datos disponibles para responder | Sistema recién iniciado, sin actividad |
| `ERR_NOT_INITIALIZED` | El sistema no se ha inicializado | `apoch` no arrancó correctamente |
| `ERR_DEPENDENCY_UNAVAILABLE` | Un módulo interno necesario no está disponible | Módulo requerido no cargado o falló |
| `ERR_PERMISSION_DENIED` | El usuario no tiene permiso para esta consulta | Restricción de acceso (futuro) |
| `ERR_INVALID_ARGUMENT` | Parámetro inválido | Tipo incorrecto, valor fuera de rango |
| `ERR_INTERNAL` | Error interno inesperado | Excepción no categorizada |
| `ERR_UNKNOWN` | Error no clasificado | Último recurso, siempre investigar |

Formato de respuesta de error:

```json
{
  "ok": false,
  "error": {
    "code": "ERR_TIMEOUT",
    "message": "No se pudo obtener el estado a tiempo. Uno o más módulos no respondieron."
  }
}
```

---

## Tool 1: `apoch_status`

**Estabilidad:** Public Stable

### 1. API Design Review

#### 1.1 Human Intent
**"¿Qué está pasando?"** — El estado general del sistema en una vista unificada.

#### 1.2 Why Public?
Es el panel principal. Cualquier usuario necesita saber si el sistema está funcionando, qué pasó recientemente y si hay algo que requiera atención.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_status` | ✅ **Seleccionado** | Intención clara: "dame el estado". Familiar para usuarios de CLI. |
| `apoch_state` | ❌ Descartado | "State" suena a implementación (máquina de estados). |
| `apoch_summary` | ❌ Descartado | Demasiado genérico. No comunica "estado actual". |

#### 1.4 Output Contract
- **Entradas**: Ninguna.
- **Salida**: Summary, Explanation, Evidence, Suggested Action, Confidence, generated_at, data_freshness.
- **Contiene**: Estado general, componentes activos, problemas detectados, actividad reciente, recomendación rápida.
- **Casos sin datos**: "Sistema iniciado, sin actividad registrada." (ERR_NO_DATA si no hay ningún módulo disponible)
- **Tiempo objetivo**: < 2 segundos.
- **Confidence**: siempre HIGH (es estado actual, no predicción).

#### 1.5 UX Validation
- **Usuario nuevo**: "Status = estado del sistema. Lo llamo cuando quiero saber si todo está bien."
- **Usuario OpenCode**: "Reemplaza vision_state. Lo uso al empezar una sesión."
- **Desarrollador Apoch**: "No expone módulos internos. Consulta Vision + Guardian + Chronicle + Oracle."

#### 1.6 Future Compatibility
El nombre `status` es estable. Se pueden añadir campos extensibles. Sigue siendo relevante en 3 años.

#### 1.7 Internal Mapping (solo mantenimiento — no público)
- Vision, Guardian, Chronicle, Oracle

#### 1.8 Acceptance Matrix
- [x] Responde intención humana
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds

#### 1.9 Anti-Patterns
No debe mostrar PID, RAM, threads, objetos Python, rutas internas, nombres de clase, módulos consultados. No debe derivar a otra tool. No debe ser un dump de `vision_state`.

#### 1.10 Definition of Done
- [x] Specification aprobada
- [x] Trazabilidad con Proposal
- [x] Criterios de aceptación verificables
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación para usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Estado General del Sistema

`apoch_status` MUST devolver un resumen ejecutivo del estado general del sistema combinando información de Vision, Guardian, Chronicle y Oracle.

Formato MUST: Summary → Explanation → Evidence → Suggested Action → Confidence → generated_at → data_freshness.

##### Scenario: Happy path — sistema saludable

- GIVEN todos los módulos están en estado `running`, sin errores activos, con actividad reciente registrada
- WHEN un agente llama `apoch_status`
- THEN la respuesta MUST incluir Summary con "🟢" o equivalente
- AND MUST incluir Explanation con contexto breve
- AND MUST incluir Evidence con componentes activos
- AND MUST incluir Suggested Action (puede ser "Ninguna acción requerida")
- AND Confidence MUST ser HIGH
- AND MUST incluir generated_at y data_freshness
- AND la respuesta MUST ser completa — no debe derivar a otra tool

##### Scenario: Sin actividad registrada

- GIVEN el sistema acaba de iniciarse y Chronicle no tiene eventos
- WHEN un agente llama `apoch_status`
- THEN la respuesta MUST indicar "Sistema iniciado, sin actividad registrada"
- AND MUST incluir estado general y componentes activos

##### Scenario: Problema detectado

- GIVEN Guardian reporta un módulo en estado `failed`
- WHEN un agente llama `apoch_status`
- THEN la respuesta MUST incluir "🟡" o "🔴" en el estado general
- AND MUST detallar el problema detectado en Evidence
- AND Confidence SHOULD reflejar la presencia de problemas

##### Scenario: Timeout en módulo interno

- GIVEN Vision no responde dentro del tiempo límite
- WHEN un agente llama `apoch_status`
- THEN la respuesta MUST devolver error con código `ERR_TIMEOUT`
- AND el error MUST indicar qué módulo no respondió (sin exponer arquitectura interna al usuario)

---

## Tool 2: `apoch_history`

**Estabilidad:** Public Stable

### 1. API Design Review

#### 1.1 Human Intent
**"¿Qué pasó?"** — Una línea de tiempo cronológica legible.

#### 1.2 Why Public?
Sin esta herramienta, el usuario debe llamar `chronicle_query` con filtros técnicos. `apoch_history` entrega una narrativa.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_history` | ✅ **Seleccionado** | Universal, comprensible. Coherente con CLI. |
| `apoch_timeline` | ❌ Descartado | Más específico (solo orden temporal). History cubre más. |
| `apoch_activity` | ❌ Descartado | Suena a actividad en vivo, no a histórico. |
| `apoch_log` | ❌ Descartado | Confunde con logs técnicos de debug. |

#### 1.4 Output Contract
- **Entradas**: Opcionales: `horas` (últimas N horas), `tipo` (lifecycle, tool, error).
- **Salida**: Summary, Explanation, Evidence (línea de tiempo narrativa), Suggested Action, Confidence, generated_at, data_freshness.
- **Prohibido**: IDs de evento, SQL, estructura de tabla, nombres de módulo internos.
- **Casos sin datos**: "No hay actividad registrada en el período solicitado."
- **Tiempo objetivo**: < 1 segundo.

#### 1.5 UX Validation
- **Usuario nuevo**: "History = lo que pasó antes. Lo uso si quiero ver qué hizo el sistema."
- **Usuario OpenCode**: "Reemplaza chronicle_query. No necesito saber los tipos de evento."
- **Desarrollador Apoch**: "No expone IDs, tablas, ni campos internos. Es narrativa pura."

#### 1.6 Future Compatibility
`history` es permanente. Se puede extender con nuevos filtros.

#### 1.7 Internal Mapping (solo mantenimiento)
- Chronicle (events), Vision (logs para enriquecer narrativa)

#### 1.8 Acceptance Matrix
- [x] Responde intención humana
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds

#### 1.9 Anti-Patterns
No debe devolver JSON de eventos crudos. No debe incluir `id`, `event_type`, `source`. No debe requerir filtros. No debe derivar a otra tool.

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Línea de Tiempo Narrativa

`apoch_history` MUST devolver una línea de tiempo cronológica en lenguaje natural, sin exponer estructuras internas de Chronicle.

##### Scenario: Happy path — actividad registrada

- GIVEN Chronicle tiene eventos registrados en las últimas 24 horas
- WHEN un agente llama `apoch_history`
- THEN la respuesta MUST ser una lista cronológica descendente en lenguaje natural
- AND cada entrada MUST ser una frase narrativa (ej: "09:15 — Módulo Vision iniciado")
- AND MUST incluir Confidence (HIGH si los datos son recientes)
- AND MUST incluir generated_at y data_freshness
- AND la respuesta MUST NOT incluir IDs de evento, SQL o nombres de tabla

##### Scenario: Filtro por horas

- GIVEN eventos en las últimas 48 horas
- WHEN un agente llama `apoch_history` con `horas=2`
- THEN la respuesta MUST contener SOLO eventos de las últimas 2 horas

##### Scenario: Sin actividad en el período

- GIVEN no hay eventos en el rango solicitado
- WHEN un agente llama `apoch_history`
- THEN la respuesta MUST indicar "No hay actividad registrada en el período solicitado"
- AND Confidence MUST ser LOW (dato negativo)

##### Scenario: Filtro por tipo de evento

- GIVEN eventos de tipos variados (lifecycle, tool, error)
- WHEN un agente llama `apoch_history` con `tipo=error`
- THEN la respuesta MUST contener solo eventos de tipo error como narrativa

---

## Tool 3: `apoch_health`

**Estabilidad:** Public Stable

### 1. API Design Review

#### 1.1 Human Intent
**"¿Tengo algún problema?"** — Diagnóstico interpretado, no técnico.

#### 1.2 Why Public?
La alternativa es leer diagnósticos crudos. `apoch_health` clasifica severidad y explica el impacto.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_health` | ✅ **Seleccionado** | Familiar: "check de salud". Responde directamente si hay problemas. |
| `apoch_diagnostics` | ❌ Descartado | Técnico. No responde "¿tengo problemas?" sino "¿qué dicen los diagnósticos?". |
| `apoch_status` | ❌ Descartado | Ya usado. Health es más específico. |

#### 1.4 Output Contract
- **Entradas**: Ninguna.
- **Salida**: Summary, Explanation, Evidence, Suggested Action, Confidence, generated_at, data_freshness.
- **Clasificación**: 🟢 Sin problemas / 🟡 Advertencias / 🔴 Problemas críticos.
- **Cada problema incluye**: impacto, explicación, posible causa, acción recomendada.
- **Casos sin datos**: 🟢 "Sin problemas detectados."
- **Tiempo objetivo**: < 2 segundos.
- **Confidence**: HIGH si hay datos de Guardian; MEDIUM si parcial; LOW si no disponible.

#### 1.5 UX Validation
- **Usuario nuevo**: "Health = revisión médica del sistema. Lo llamo si sospecho que algo anda mal."
- **Usuario OpenCode**: "Antes miraba guardian_diagnostics. Ahora health me dice si hay problemas sin que entienda el formato."
- **Desarrollador Apoch**: "El usuario no ve ModuleDiagnostics. Solo ve severidad + qué hacer."

#### 1.6 Future Compatibility
Clasificación 🟢/🟡/🔴 extensible. `health` es permanente.

#### 1.7 Internal Mapping (solo mantenimiento)
- Guardian (diagnostics), Vision (estado de módulos)

#### 1.8 Acceptance Matrix
- [x] Responde intención humana
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds

#### 1.9 Anti-Patterns
No debe devolver tracebacks, nombres de módulo internos, códigos de error internos. No debe derivar a otra tool. No debe exponer ModuleDiagnostics.

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Clasificación de Severidad

`apoch_health` MUST clasificar el estado del sistema en 🟢/🟡/🔴, e incluir para cada problema: impacto, explicación, posible causa y acción recomendada. Formato MUST: Summary → Explanation → Evidence → Suggested Action → Confidence → generated_at → data_freshness.

##### Scenario: Happy path — sin problemas

- GIVEN Guardian no reporta módulos en estado `failed` ni advertencias activas
- WHEN un agente llama `apoch_health`
- THEN la respuesta MUST ser "🟢 Sin problemas detectados" en Summary
- AND Confidence MUST ser HIGH

##### Scenario: Advertencia activa

- GIVEN Vision reporta un módulo degradado pero funcionando
- WHEN un agente llama `apoch_health`
- THEN la respuesta MUST ser "🟡" en el estado general
- AND MUST incluir Suggested Action con qué hacer

##### Scenario: Problema crítico

- GIVEN Guardian tiene un módulo en estado `failed`
- WHEN un agente llama `apoch_health`
- THEN la respuesta MUST ser "🔴"
- AND MUST incluir posible causa y acción recomendada

##### Scenario: Guardian no disponible

- GIVEN Guardian no está disponible
- WHEN un agente llama `apoch_health`
- THEN la respuesta MUST usar `ERR_DEPENDENCY_UNAVAILABLE`
- AND Confidence MUST ser LOW

---

## Tool 4: `apoch_recommend`

**Estabilidad:** Public Stable

### 1. API Design Review

#### 1.1 Human Intent
**"¿Cuál es la siguiente acción de mayor impacto que debería realizar ahora?"**

Esta es la ÚNICA pregunta que responde. No responde estado, salud, historial, métricas, insights ni logs.

#### 1.2 Why Public?
Es la herramienta más importante del sistema. Sin ella, el usuario debe interpretar estado, historial, salud y métricas para decidir el próximo paso.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_recommend` | ✅ **Seleccionado** | "Recommend" = sugerencia accionable. El verbo invita a actuar. |
| `apoch_advise` | ❌ Descartado | Demasiado formal. "Advise" suena a consultoría. |
| `apoch_next` | ❌ Descartado | Podría confundirse con navegación (next/previous). |
| `apoch_guide` | ❌ Descartado | Suena a tutorial, no a recomendación contextual. |

#### 1.4 Output Contract

**Contrato ESTRICTO — no se desvía:**

```
Next Action:  <acción concreta>
Why:          <por qué esta acción es la de mayor impacto>
Priority:     HIGH | MEDIUM | LOW
Confidence:   <0.00–1.00>
Generated:    <timestamp ISO 8601>
Data Fresh:   <segundos>
```

**LÍMITES EXPLÍCITOS — `apoch_recommend` NUNCA responde:**

| Esto | Pertenece a |
|------|-------------|
| Estado del sistema | `apoch_status` |
| Salud / problemas | `apoch_health` |
| Historial de actividad | `apoch_history` |
| Métricas de productividad | `apoch_progress` |
| Patrones de mejora general | `apoch_insights` |
| Logs técnicos | `apoch_logs` |
| Ejecutar cambios | (acción futura, no implementada) |

- **Entradas**: Ninguna (usa estado actual autónomamente).
- **Casos sin recomendaciones**: "No hay recomendaciones en este momento. El sistema opera dentro de parámetros normales." (Confidence: HIGH — es una certeza, no una adivinanza)
- **Tiempo objetivo**: < 5 segundos.
- **Si no puede determinar**: Confidence LOW o MEDIUM, con Explanation indicando por qué.

##### Qué PUEDE incluir (opcional, solo si aporta):
- Expected benefit: una línea describiendo el impacto positivo

##### Qué NUNCA incluye:
- Estado de módulos, diagnósticos, eventos, métricas, patrones, logs, módulos consultados, orden de ejecución

#### 1.5 UX Validation
- **Usuario nuevo**: "Recommend = me dice qué hacer. Ideal si no sé por dónde seguir."
- **Usuario OpenCode**: "Antes revisaba Oracle, Optimizer y Guardian. Ahora una sola llamada."
- **Desarrollador Apoch**: "Orquesta Oracle + Optimizer + Pulse + Guardian + Vision. El usuario no lo sabe ni debe saberlo."

#### 1.6 Future Compatibility
`recommend` admite expansión controlada: nuevas fuentes de recomendación sin cambiar el contrato de salida.

#### 1.7 Internal Mapping (solo mantenimiento)
- Oracle, Optimizer, Pulse, Guardian, Vision

#### 1.8 Acceptance Matrix
- [x] Responde intención humana (una específica, no varias)
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds

#### 1.9 Anti-Patterns
No debe responder estado, salud, historial, métricas, insights, logs. No debe ejecutar cambios. No debe enumerar módulos. No debe exponer el orden de ejecución de módulos internos. No debe derivar a otra tool.

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Recomendación de Siguiente Acción

`apoch_recommend` MUST devolver la siguiente acción de mayor impacto basada en el estado actual del sistema. La respuesta MUST limitarse a: Next Action, Why, Priority, Confidence, Generated, Data Fresh.

##### Scenario: Happy path — recomendación disponible

- GIVEN Oracle tiene una recomendación activa priorizada
- WHEN un agente llama `apoch_recommend`
- THEN la respuesta MUST incluir "Next Action" con una acción concreta
- AND MUST incluir "Why" explicando por qué es la de mayor impacto
- AND MUST incluir "Priority" (HIGH/MEDIUM/LOW)
- AND MUST incluir "Confidence" como número entre 0.00 y 1.00
- AND MUST incluir "Generated" y "Data Fresh"
- AND la respuesta MUST NOT incluir estado, salud, historial ni módulos

##### Scenario: Sin recomendaciones

- GIVEN todos los módulos reportan operación normal sin oportunidades detectadas
- WHEN un agente llama `apoch_recommend`
- THEN la respuesta MUST indicar "No hay recomendaciones en este momento. El sistema opera dentro de parámetros normales."
- AND Confidence MUST ser HIGH (es una certeza)

##### Scenario: Datos insuficientes

- GIVEN el sistema acaba de iniciar y no hay datos históricos
- WHEN un agente llama `apoch_recommend`
- THEN la respuesta MUST tener Confidence LOW o MEDIUM
- AND MUST incluir Explanation indicando por qué la confianza es limitada

##### Scenario: Oracle no disponible

- GIVEN Oracle no está disponible pero otros módulos sí
- WHEN un agente llama `apoch_recommend`
- THEN la respuesta MUST degradar gracefulmente usando módulos disponibles
- AND Confidence MUST reflejar la degradación (MEDIUM o LOW)
- AND MUST NOT exponer qué módulo falló

---

## Tool 5: `apoch_progress`

**Estabilidad:** 🧪 Experimental

### 1. API Design Review

#### 1.1 Human Intent
**"¿Cómo voy?"** — Productividad, evolución y tendencias interpretadas.

#### 1.2 Why Public?
Los datos de Pulse deben ser interpretados, no expuestos como números crudos. Responde una pregunta humana sobre el avance.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_progress` | ✅ **Seleccionado** (candidato) | Responde "¿cómo voy?". Orientado a personas. |
| `apoch_pulse` | ❌ Descartado | Expone el nombre del módulo interno. |
| `apoch_stats` | ❌ Descartado | Técnico. "Stats" = estadísticas, no progreso. |
| `apoch_productivity` | ❌ Descartado | Demasiado largo. Menos descubrible. |

**Nota:** El nombre `apoch_progress` es candidato. Podría cambiarse al estabilizarse si se encuentra un nombre más intuitivo.

#### 1.4 Output Contract
- **Entradas**: Opcional: `periodo` (hoy, semana, mes).
- **Salida**: Summary, Explanation, Evidence, Suggested Action, Confidence, generated_at, data_freshness.
- **Prohibido**: WorkUnit IDs, costes por token, nombres de modelo, filtros técnicos.
- **Casos sin datos**: "No hay datos de actividad en el período seleccionado."
- **Tiempo objetivo**: < 2 segundos.

#### 1.5 UX Validation
- **Usuario nuevo**: "Progress = mi avance. Lo uso para saber si estoy siendo productivo."
- **Usuario OpenCode**: "Pulse me daba números. Progress me da interpretación."
- **Desarrollador Apoch**: "No expone WorkUnit ni métricas internas."

#### 1.6 Future Compatibility
Admite objetivos, comparativas, proyecciones.

#### 1.7 Internal Mapping (solo mantenimiento)
- Pulse (measurements, analysis)

#### 1.8 Acceptance Matrix
- [x] Responde intención humana
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds

#### 1.9 Anti-Patterns
No debe mostrar WorkUnit IDs, costes por token, nombres de modelo. No debe requerir filtros técnicos. No debe derivar a otra tool.

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Resumen de Progreso

`apoch_progress` MUST devolver un resumen interpretado de productividad y evolución basado en datos de Pulse. Formato MUST alinearse al estándar (Summary → Explanation → Evidence → Suggested Action → Confidence → generated_at → data_freshness) al pasar a Public Stable.

##### Scenario: Happy path — datos disponibles

- GIVEN Pulse tiene mediciones de la sesión actual
- WHEN un agente llama `apoch_progress`
- THEN la respuesta MUST incluir un resumen de productividad en Summary
- AND MUST incluir tendencias interpretadas en Evidence

##### Scenario: Período sin datos

- GIVEN no hay mediciones en el período solicitado
- WHEN un agente llama `apoch_progress` con `periodo=mes`
- THEN la respuesta MUST indicar "No hay datos de actividad en el período seleccionado"

##### Scenario: Tendencia negativa

- GIVEN las mediciones muestran una disminución en productividad
- WHEN un agente llama `apoch_progress`
- THEN la respuesta MUST incluir la tendencia detectada
- AND MUST incluir una interpretación (no solo el número)

---

## Tool 6: `apoch_insights`

**Estabilidad:** 🧪 Experimental — **Alta probabilidad de redefinición antes de Public Stable**

### 1. API Design Review

#### 1.1 Human Intent
**"¿Qué patrones detectaste?"** — Oportunidades de mejora basadas en patrones de uso.

**Nota de diseño:** La intención original "¿Cómo puedo mejorar?" resultó ser demasiado abstracta. Los usuarios no preguntan "dame insights". Preguntan "¿por qué estoy lento?", "¿qué estoy haciendo mal?", "¿qué puedo optimizar?". Esta tool está en Experimental precisamente para resolver su intención real antes de estabilizarse.

Posibles redefiniciones futuras:
- Fusionarse con `apoch_recommend` como modo "tendencias"
- Renombrarse a `apoch_patterns` (más concreto)
- Renombrarse a `apoch_audit` (si el foco es revisión de hábitos)

#### 1.2 Why Public? (condicional)
Sin esta herramienta, las hipótesis de Optimizer quedan inaccesibles. Sin embargo, su valor real debe demostrarse con uso antes de pasar a Public Stable.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_insights` | ✅ **Seleccionado (candidato)** | "Insights" = hallazgos significativos. No sugiere ejecución. Pendiente de validación. |
| `apoch_optimize` | ❌ Descartado | Sugiere ejecutar cambios. |
| `apoch_suggest` | ❌ Descartado | Demasiado genérico. |
| `apoch_patterns` | 🟡 Pendiente | Alternativa viable si se confirma que el valor está en patrones. |

#### 1.4 Output Contract
- **Entradas**: Ninguna.
- **Salida**: Summary, Explanation, Evidence (patrones, oportunidades, sugerencias), Suggested Action, Confidence, generated_at, data_freshness.
- **No ejecuta cambios. No modifica estado.**
- **Casos sin datos**: "No se detectaron patrones ni oportunidades de mejora."
- **Tiempo objetivo**: < 3 segundos.

#### 1.5 UX Validation
- **Usuario nuevo**: Dudoso. "Insights" no es una palabra que un usuario nuevo use espontáneamente.
- **Usuario OpenCode**: "Optimizer me daba hipótesis técnicas. Insights me da recomendaciones prácticas."
- **Desarrollador Apoch**: "No expone OptimizationHypothesis ni confianza estadística."

**Conclusión UX:** Esta tool necesita validación con usuarios reales antes de estabilizarse. El nombre y alcance pueden cambiar.

#### 1.6 Future Compatibility
El nombre `insights` es lo suficientemente genérico para no romper clientes si se redefine el alcance.

#### 1.7 Internal Mapping (solo mantenimiento)
- Optimizer (hypotheses, baselines), Pulse (measurements)

#### 1.8 Acceptance Matrix
- [x] Responde intención humana (aunque la intención exacta está en revisión)
- [x] Útil por sí sola
- [x] No expone arquitectura
- [x] Salida consistente
- [x] Descubrible (parcial — el nombre no es óptimo)
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada (pendiente de confirmación)
- [x] Rule of 30 Seconds (parcial — "insights" puede no ser obvio)

#### 1.9 Anti-Patterns
No debe ejecutar cambios. No debe modificar estado. No debe devolver confianza estadística cruda. No debe superponerse con `apoch_recommend` (si la recomendación es accionable ahora, pertenece a recommend).

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Oportunidades de Mejora

`apoch_insights` MUST devolver oportunidades de mejora basadas en hipótesis de Optimizer y datos de Pulse, sin ejecutar cambios ni modificar estado.

##### Scenario: Happy path — oportunidades detectadas

- GIVEN Optimizer tiene hipótesis activas con `confidence > 0.5`
- WHEN un agente llama `apoch_insights`
- THEN la respuesta MUST incluir oportunidades de mejora en Evidence
- AND MUST incluir patrones detectados (si existen)

##### Scenario: Sin oportunidades

- GIVEN Optimizer no tiene hipótesis activas
- WHEN un agente llama `apoch_insights`
- THEN la respuesta MUST indicar "No se detectaron patrones ni oportunidades de mejora"

##### Scenario: Optimizer no disponible

- GIVEN Optimizer no está cargado
- WHEN un agente llama `apoch_insights`
- THEN la respuesta MUST usar `ERR_DEPENDENCY_UNAVAILABLE`

##### Scenario: Recomendación vs insight

- GIVEN existe una hipótesis sobre lentitud en el editor
- WHEN un agente pregunta "¿qué debería hacer ahora?" (recommend)
- Y otro agente pregunta "¿qué patrones ves?" (insights)
- THEN recommend MUST devolver una acción concreta ("Cerrar pestañas no utilizadas")
- AND insights MUST devolver el patrón detectado ("Aumento del 18% en tiempo de respuesta en sesiones largas")
- AND ambas respuestas NO DEBEN superponerse ni contradecirse

---

## Tool 7: `apoch_logs`

**Estabilidad:** ⚡ Advanced

### 1. API Design Review

#### 1.1 Human Intent
**"Necesito ver los logs del sistema para depurar."**

#### 1.2 Why Public? (Advanced)
Desarrolladores que mantienen Apoch-AI necesitan acceso a logs estructurados. Es Advanced porque su audiencia es técnica.

#### 1.3 Alternative Names
| Nombre | Veredicto | Motivo |
|--------|-----------|--------|
| `apoch_logs` | ✅ **Seleccionado** | Familiar. Todo desarrollador sabe qué es "logs". Coherente con CLI. |
| `apoch_debug` | ❌ Descartado | Demasiado genérico. |
| `apoch_trace` | ❌ Descartado | Más específico (trazas). Logs cubre más. |

#### 1.4 Output Contract
- **Entradas**: `nivel` (INFO, WARN, ERROR, FATAL), `limite`, `modulo` — todos opcionales.
- **Salida**: Entradas de log formateadas con timestamp, nivel, mensaje, Confidence, generated_at, data_freshness.
- **Casos sin datos**: "No hay entradas de log que coincidan con los filtros especificados."
- **Tiempo objetivo**: < 1 segundo.

#### 1.5 UX Validation
- **Usuario nuevo**: "Logs = para desarrolladores. No lo usaría normalmente."
- **Usuario OpenCode**: "Cuando algo falla, veo logs."
- **Desarrollador Apoch**: "Filtros claros, formato estándar."

#### 1.6 Future Compatibility
`logs` es el estándar universal. Se puede extender con búsqueda full-text, rangos de tiempo, exportación.

#### 1.7 Internal Mapping (solo mantenimiento)
- Vision (logs buffer)

#### 1.8 Acceptance Matrix
- [x] Responde intención humana
- [x] Útil por sí sola
- [x] No expone arquitectura interna
- [x] Salida consistente
- [x] Descubrible (desarrolladores)
- [x] Compatible hacia atrás
- [x] Escala a futuro
- [x] UX validada
- [x] Rule of 30 Seconds (perfil desarrollador)

#### 1.9 Anti-Patterns
No debe ser la herramienta principal para usuarios normales. No debe exponer formato interno de almacenamiento. No debe derivar a otra tool.

#### 1.10 Definition of Done
- [x] Specification
- [x] Trazabilidad
- [x] Criterios de aceptación
- [x] Escenarios de prueba
- [x] Casos negativos
- [x] Documentación usuarios
- [x] Documentación técnica
- [x] Auditoría SDD
- [x] Revisión UX

### 2. Requirements & Scenarios

#### Requirement: Logs Técnicos

`apoch_logs` MUST devolver entradas de log filtrables por nivel, módulo y límite, formateadas de forma legible para desarrolladores.

##### Scenario: Happy path — logs con filtros

- GIVEN hay entradas de log de varios niveles y módulos
- WHEN un agente llama `apoch_logs` con `nivel=ERROR`
- THEN la respuesta MUST contener solo entradas de nivel ERROR
- AND MUST incluir timestamp, nivel y mensaje por entrada

##### Scenario: Sin resultados

- GIVEN no hay entradas de log del nivel solicitado
- WHEN un agente llama `apoch_logs` con `nivel=FATAL`
- THEN la respuesta MUST indicar "No hay entradas de log que coincidan con los filtros especificados"

##### Scenario: Límite aplicado

- GIVEN hay 100 entradas de log
- WHEN un agente llama `apoch_logs` con `limite=5`
- THEN la respuesta MUST contener máximo 5 entradas (las más recientes)

##### Scenario: Sin filtros

- GIVEN hay entradas de log recientes
- WHEN un agente llama `apoch_logs` sin parámetros
- THEN la respuesta MUST devolver las últimas 50 entradas por defecto

---

## Architecture Review — Cross-Tool Analysis

### Overlaps / Duplicación

| Herramientas | ¿Overlap? | Decisión |
|-------------|-----------|----------|
| `status` ↔ `health` | Potencial parcial | `status` = vista general. `health` = solo problemas. Separación clara. |
| `history` ↔ `logs` | Diferente audiencia | `history` = narrativa (todos). `logs` = debug (desarrolladores). |
| `recommend` ↔ `insights` | Complementarias | `recommend` = "qué hacer AHORA". `insights` = patrones GENERALES. Límite temporal. |
| `progress` ↔ `insights` | Bajo | `progress` = pasado-presente. `insights` = futuro-mejora. |

**Veredicto:** No hay duplicación funcional. Cada herramienta responde una pregunta humana distinta.

### Naming Consistency

- **Public Stable** (4): `apoch_status`, `apoch_history`, `apoch_health`, `apoch_recommend`
- **Experimental** (2): `apoch_progress`, `apoch_insights`
- **Advanced** (1): `apoch_logs`

Consistencia: prefijo `apoch_` + nombre UNIX-compatible. Buenos nombres cortos (< 15 caracteres).

### Intent Stability Rule — Verificación

| Tool | ¿Sobrevive si eliminamos Oracle? | ¿Sobrevive si eliminamos Pulse? | ¿Sobrevive si eliminamos Guardian? |
|------|-------------------------------|------------------------------|----------------------------------|
| `apoch_status` | ✅ Sí (solo perdería recomendación rápida) | ✅ Sí | ✅ Sí (salud degradada) |
| `apoch_history` | ✅ Sí | ✅ Sí | ✅ Sí |
| `apoch_health` | ✅ Sí | ✅ Sí | ❌ Depende de Guardian (pero es su propósito) |
| `apoch_recommend` | ⚠️ Degradado | ⚠️ Degradado | ⚠️ Degradado |
| `apoch_progress` | ✅ Sí | ❌ Depende de Pulse | ✅ Sí |
| `apoch_insights` | ✅ Sí | ⚠️ Degradado | ✅ Sí |
| `apoch_logs` | ✅ Sí | ✅ Sí | ✅ Sí |

**Veredicto:** El nombre y propósito de cada tool sobrevive aunque cambie la implementación. **Intent Stability Rule se cumple.**

### Future Extensions

| Área | Tool candidata | Intención humana |
|------|---------------|-----------------|
| Configuración | `apoch_config` | "¿Cómo configuro?" (Future) |
| Alertas | `apoch_alerts` | "¿Qué necesita atención?" (Future) |
| Comandos | `apoch_exec` | "Quiero ejecutar una acción" (Future) |
| Identidad | `apoch_whoami` | "¿Quién soy?" (Future) |

### Catálogo Global de Errores — Cobertura

| Código | ¿Usado por alguna tool? |
|--------|------------------------|
| `ERR_TIMEOUT` | ✅ status, recommend |
| `ERR_NO_DATA` | ✅ history, progress, insights, logs |
| `ERR_NOT_INITIALIZED` | ✅ Todas (sistema no arrancado) |
| `ERR_DEPENDENCY_UNAVAILABLE` | ✅ health, insights |
| `ERR_PERMISSION_DENIED` | 🔲 Futuro |
| `ERR_INVALID_ARGUMENT` | ✅ logs (filtro inválido) |
| `ERR_INTERNAL` | ✅ Todas (catch-all) |
| `ERR_UNKNOWN` | ✅ Todas (último recurso) |

### Plan de Migración

| Tool actual | Reemplazo | Acción |
|------------|-----------|--------|
| `vision_state` | `apoch_status` | Backward compat alias |
| `chronicle_query` | `apoch_history` | Backward compat alias |
| `guardian_diagnostics` | `apoch_health` | Backward compat alias |
| `guardian_all_diagnostics` | `apoch_health` | Redirigir (fusionado) |
| *(nueva)* | `apoch_recommend` | Crear desde cero |
| *(nueva)* | `apoch_progress` | Crear desde cero (Experimental) |
| *(nueva)* | `apoch_insights` | Crear desde cero (Experimental — sujeto a redefinición) |
| `vision_logs` | `apoch_logs` | Backward compat alias |
| `vision_config` | 🔒 Internal | Eliminar de MCP público |
| `chronicle_record` | 🔒 Internal | Eliminar de MCP público |
| `chronicle_stats` | ⚡ Advanced | Mantener como Advanced o fusionar en history |
| `guardian_clear_*` | 🔄 Automática | Mover a interno |
| `vision_system` | 🗑️ Eliminar | Contenido redundante |
