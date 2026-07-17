---
title: "API Boundary Review — apoch_history"
status: draft
phase: review
created: 2026-07-16
reviewers:
  - gentle-orchestrator
change: mcp-tools-redesign
---

# API Boundary Review — `apoch_history`

> **Propósito de este documento:** Verificar que el diseño de `apoch_history` (PR4) es mínimo, enfocado y no invade el territorio de otras herramientas de la API pública. Esto es un análisis exclusivo. No inicia implementación.

---

## 1. Responsabilidad exacta

**Una sola frase:** Proveer una línea de tiempo cronológica en lenguaje natural de la actividad registrada del sistema, con filtros opcionales de ventana temporal y tipo de evento, sin diagnosticar causas, sin recomendar acciones, sin medir productividad, sin mostrar logs técnicos, sin mostrar el estado actual del sistema y sin exponer implementación interna.

### Regla de pertenencia

| Pregunta | Responde | Si no, pertenece a |
|---|---|---|
| "¿Qué pasó?" (en cualquier rango temporal) | ✅ `apoch_history` | — |
| "¿Qué está pasando ahora?" | ❌ No — estado actual | `apoch_status` |
| "¿Tengo algún problema?" | ❌ No — diagnóstico | `apoch_health` |
| "¿Qué debería hacer ahora?" | ❌ No — recomendación priorizada | `apoch_recommend` |
| "¿Cómo voy?" | ❌ No — productividad/tendencias | `apoch_progress` |
| "¿Qué patrones ves?" | ❌ No — patrones/oportunidades | `apoch_insights` |
| "Dame los logs del sistema" | ❌ No — debugging técnico | `apoch_logs` |

---

## 2. Módulos que consulta

### 2.1 Mapa de módulos

| Módulo | Clasificación | Datos que aporta | Justificación |
|---|---|---|---|
| **Chronicle** | **Obligatorio** | Eventos de actividad (`query` con EventFilter): eventos de lifecycle, tool_invocation, error, con timestamp, tipo, severidad y payload | Sin Chronicle no hay historial. Es la fuente primaria y única esencial de history. El propósito mismo de history es traducir eventos de Chronicle a narrativa humana. |
| **Vision** | **Opcional** | Logs del sistema (`logs` buffer o similar): datos de log para enriquecer la narrativa de eventos | Aporta contexto adicional para crear narrativas más ricas. No es requerido porque Chronicle ya contiene la información esencial de eventos. Vision enriquece pero no define. |
| **Guardian** | **Nunca** | Diagnósticos, módulos en FAILED | Guardian responde a "¿tengo algún problema?" (health). Los diagnósticos no son eventos históricos. |
| **Oracle** | **Nunca** | Recomendaciones, predicciones | Oracle responde a "¿qué debería hacer?" (recommend). No aporta al historial. |
| **Pulse** | **Nunca** | Mediciones de productividad | Pulse responde a "¿cómo voy?" (progress). Las mediciones no son eventos históricos. |
| **Optimizer** | **Nunca** | Hipótesis, patrones | Optimizer responde a "¿qué patrones ves?" (insights). No aporta al historial de eventos. |

### 2.2 Justificación detallada de módulos "Nunca"

#### Guardian
**Riesgo:** Si history consultara Guardian, podría mezclar diagnósticos con eventos históricos. Un usuario podría ver "módulo X en FAILED" como un evento más, cuando eso es un diagnóstico que pertenece a `health`.

**Límite estricto:** History muestra eventos ocurridos. Guardian reporta diagnósticos del momento actual. Son naturalezas distintas. Si un módulo falló y se registró como evento en Chronicle, history lo mostrará como evento (ej. "14:30 — Error en sistema de monitoreo"). No necesita consultar a Guardian para eso.

#### Oracle
**Riesgo:** Oracle podría sugerir "revisa el evento X porque es importante". Eso sería una recomendación incrustada en el historial.

**Límite estricto:** History presenta eventos en orden cronológico. No los prioriza, no los evalúa, no recomienda acciones basadas en ellos.

#### Pulse
**Riesgo:** Si history incluyera métricas de productividad asociadas a eventos (ej. "completaste 3 tareas en esta hora"), estaría invadiendo `progress`.

**Límite estricto:** History trabaja con eventos discretos, no con agregaciones ni mediciones continuas.

#### Optimizer
**Riesgo:** Optimizer podría identificar que "los errores aumentan los viernes" y history podría mostrar eso como parte de la línea de tiempo. Eso es detección de patrones, no historial.

**Límite estricto:** History muestra eventos, no patrones. La interpretación de patrones pertenece a `insights`.

### 2.3 Referencias a spec y ADRs

| Decisión | Referencia | Impacto |
|---|---|---|
| Chronicle obligatorio | Spec §1.7 (Internal Mapping): "Chronicle (events)" | History no funciona sin Chronicle |
| Vision opcional | Spec §1.7: "Vision (logs para enriquecer narrativa)" | Vision enriquece pero no es requerido |
| ServiceRegistry tipado | ADR-001 | History recibe servicios duck-typed |
| Timeout Chronicle 0.5s | ADR-001 design docstring | Chronicle debe responder en 0.5s |
| Timeout Vision 0.5s | ADR-001 design docstring | Vision debe responder en 0.5s (opcional) |
| Chronicle timeout → ERR_DEPENDENCY_UNAVAILABLE | ADR-001 design docstring | Sin Chronicle, history no puede funcionar |
| Vision timeout → respuesta solo con Chronicle | ADR-001 design docstring | Degradación graceful |

---

## 3. Información que puede mostrar exactamente

### 3.1 Obligatoria (siempre presente)

| Campo | Origen | Descripción |
|---|---|---|
| `api_version` | Constante | Siempre `"1.0"` (ADR-005) |
| `summary` | Coordinator | Frase resumen. Ej: "Se registraron 12 eventos en las últimas 24 horas" / "3 eventos de tipo error en la última hora" |
| `explanation` | Coordinator | Contexto breve del período consultado. Ej: "Actividad entre 2026-07-15 14:00 y 2026-07-16 14:00" |
| `evidence` | Chronicle (+ Vision opcional) | Lista de `EvidenceSource` con los datos que respaldan la respuesta |
| `confidence` | Coordinator | Nivel de confianza (`0.00`–`1.00`). HIGH cuando Chronicle responde; menor si datos parciales o sin datos |
| `generated_at` | Coordinator | Timestamp ISO 8601 de generación |
| `data_freshness` | Coordinator | Antigüedad máxima de los datos fuente en segundos |

### 3.2 Obligatoria condicional (cuando hay eventos que mostrar)

| Información | Condición | Descripción |
|---|---|---|
| Línea de tiempo narrativa | Chronicle responde con ≥1 evento | Lista cronológica descendente (más reciente primero) de eventos en lenguaje natural. Cada entrada es una frase como "09:15 — Sistema de monitoreo iniciado". |
| Cantidad de eventos | Chronicle responde | Número total de eventos en el período consultado |
| Rango temporal del historial | Filtros `horas` o implícito | Período de tiempo que cubre la respuesta. Puede estar en `summary` o `explanation`. |

### 3.3 Opcional (valor añadido si Vision responde)

| Información | Dependencia | Comportamiento si no disponible |
|---|---|---|
| Narrativa enriquecida con contexto adicional | Vision (`logs` buffer o similar) | History funciona solo con Chronicle. La narrativa se construye exclusivamente con datos de eventos. |
| Detalle adicional en entradas narrativas | Vision | Vision puede agregar contexto (ej: "09:15 — Sistema de monitoreo iniciado (carga completada en 2.3s)") |

### 3.4 Formato de la línea de tiempo

Cada entrada en la línea de tiempo DEBE ser una frase narrativa. Ejemplos válidos:

```
- 14:30 — Error en sistema de monitoreo: conexión perdida con el servicio de base de datos
- 14:25 — Herramienta de consulta invocada por agente principal
- 14:20 — Sistema de ejecución iniciado correctamente
- 13:15 — Advertencia de rendimiento detectada
```

**NO válido** (expone estructura interna):
```
- id: abc123, type: tool_invocation, source: chronicle, timestamp: 2026-07-16T14:25:00
```

---

## 4. Información que NUNCA debe mostrar

| Información | Motivo | Pertenece a |
|---|---|---|
| IDs de evento (`ActivityEvent.id`) | Viola §1.4 (Prohibido: IDs de evento) | — (nunca público) |
| SQL, nombres de tabla, estructura de DB | Viola §1.4 (Prohibido: SQL, estructura de tabla) | — (nunca público) |
| Nombres de módulo internos en texto narrativo | Viola P6 (nunca expone implementación). Los nombres de módulo solo aparecen en `evidence[].source` como identificador técnico, NO en `summary`, `explanation` ni la narrativa. | — |
| `event_type`, `source`, `severity` como campos crudos | Viola §1.9 (Anti-Patterns: "No debe incluir id, event_type, source") | — |
| Tracebacks, stack traces | Viola §1.9 (Anti-Patterns) | — |
| Payload interno de eventos (`ActivityEvent.payload`) | Viola P6; expone datos internos no diseñados para consumo público | — (nunca público) |
| Diagnóstico de problemas | No es historial; es estado actual + causas | `apoch_health` |
| Recomendaciones ("deberías hacer X") | No es historial; es acción futura | `apoch_recommend` |
| Productividad ("completaste N tareas") | No es historial; es métrica de avance | `apoch_progress` |
| Patrones ("los errores aumentan los viernes") | No es historial; es análisis de patrones | `apoch_insights` |
| Logs técnicos crudos (nivel, timestamp, mensaje) | No es narrativa; es debugging | `apoch_logs` |
| Estado actual ("módulo X está running") | No es historial; es estado presente | `apoch_status` |
| Configuración de módulos | Es Internal | — |
| Orden de ejecución de módulos | Viola ADR-007 | — |
| Confidence estadística cruda (p-values, sample sizes) | Viola P6 | — |

---

## 5. Límite preciso: "actividad reciente" (status) vs "historial" (history)

**Este es el punto MÁS CRÍTICO del review.**

### 5.1 La línea exacta

La línea se traza en **TRES dimensiones: alcance temporal, cantidad de eventos y capacidad de filtrado**:

| Dimensión | `apoch_status` (actividad reciente) | `apoch_history` (historial) |
|---|---|---|
| **Propósito** | "¿Qué pasó recientemente?" — instantánea de actividad reciente como parte de una vista general | "¿Qué pasó?" — línea de tiempo completa con alcance definido por el usuario |
| **Ventana temporal** | `STATUS_RECENT_WINDOW_MINUTES` = **5 minutos** máximo. Fijo, no configurable. | Definida por el parámetro `horas`. Sin `horas`, se usa un valor por defecto (24h propuesto). |
| **Límite de eventos** | `STATUS_RECENT_EVENTS_LIMIT` = **5 eventos** máximo. Fijo, no configurable. | `HISTORY_DEFAULT_LIMIT` = 50 propuesto. Máximo 200. |
| **Filtros** | Ninguno. Sin parámetros. | Opcionales: `horas` (ventana temporal), `tipo` (lifecycle/tool/error). |
| **Formato** | Una línea corta en `explanation`. Ej: "actividad reciente disponible" | Línea de tiempo completa en narrativa. Cada evento es una entrada. |
| **Qué gana** | El que tenga MENOS eventos entre límite y ventana. Máximo 5 eventos en 5 min. | La ventana temporal especificada. Sin límite de eventos duro (pero con default sensato). |
| **Invade history si...** | Muestra más de 5 eventos, más de 5 minutos, o acepta filtros. | — |
| **Invade status si...** | Muestra menos de 5 minutos sin filtros. Nunca, porque history no responde "qué pasa ahora" sino "qué pasó". |

### 5.2 Regla de tres líneas

```
             STATUS                    HISTORY
        ┌──────────────┐         ┌─────────────────────┐
        │  Ahora mismo  │         │  Cualquier rango    │
        │  ≤ 5 eventos  │         │  Con/sin filtros    │
        │  ≤ 5 minutos  │         │  Narrativa completa  │
        │  Sin filtros   │         │                     │
        └──────────────┘         └─────────────────────┘
               │                          │
               └──── NO SOLAPAMIENTO ─────┘
```

### 5.3 Límites de history

**Situación actual en los artefactos:**

| Aspecto | Spec | Diseño (ADR-001) | Chronicle subyacente |
|---|---|---|---|
| `horas` por defecto si se omite | **NO ESPECIFICADO** | N/A (parámetro opcional) | N/A |
| Límite de eventos por defecto | **NO ESPECIFICADO** | N/A | `EventFilter.limit` = **100** |
| Ventana temporal por defecto | **NO ESPECIFICADO** | N/A | Sin ventana (desde siempre) |
| Máximo de eventos permitido | **NO ESPECIFICADO** | N/A | Sin límite superior (el cliente DB puede manejar miles) |

**Esto es una zona gris CRÍTICA.** Si `history()` se llama sin parámetros, la implementación actual de Chronicle devolvería hasta 100 eventos desde el inicio de los tiempos. Esto no es aceptable para una herramienta Public Stable.

**Recomendación para PR4:**

1. **`horas` por defecto = 24** (últimas 24 horas). Documentado en spec y código.
2. **Límite de eventos por defecto = 50** (suficiente para una vista histórica sin ser abrumador). Documentado como `HISTORY_DEFAULT_LIMIT`.
3. **Límite máximo de eventos = 200** (para evitar lecturas masivas). Documentado como `HISTORY_MAX_LIMIT`.
4. **Nuevas constantes en `coordinator.py`:**

```python
HISTORY_DEFAULT_HOURS: int = 24
HISTORY_DEFAULT_LIMIT: int = 50
HISTORY_MAX_LIMIT: int = 200
```

### 5.4 ¿Existe solapamiento real o potencial?

**No hay solapamiento real** con los límites actuales de status (5 eventos, 5 minutos). History, incluso con valores conservadores (default 24h, 50 eventos), opera en un rango completamente diferente.

**Potencial solapamiento solo si:**

1. Alguien configura `STATUS_RECENT_WINDOW_MINUTES` a un valor grande (ej. 60 minutos) — pero es una constante fija en código, no configurable por el usuario.
2. Alguien llama `history(horas=0.08)` (~5 minutos) — pero sigue siendo histórico explícitamente solicitado, no estado actual. Aunque el rango sea el mismo, la INTENCIÓN es diferente.

**Conclusión:** No hay solapamiento real. El diseño es sólido siempre que se definan los valores por defecto faltantes.

### 5.5 ¿Qué pasa si alguien llama `history()` sin filtros?

**Comportamiento esperado (con las constantes propuestas):**

1. Se usa `HISTORY_DEFAULT_HOURS = 24` como ventana temporal.
2. Se usa `HISTORY_DEFAULT_LIMIT = 50` como límite de eventos.
3. Se consulta a Chronicle con `since = now - 24h` y `limit = 50`.
4. Se devuelven los eventos encontrados como narrativa, máximo 50.

**Comportamiento sin las constantes propuestas (riesgo actual):**

1. No se pasa `since` a Chronicle → se consultan eventos desde el inicio de los tiempos.
2. Se usa `EventFilter.limit = 100` (default de Chronicle).
3. Se devuelven hasta 100 eventos en narrativa.
4. **Problema:** Performance degradada, respuesta muy larga, consume ancho de banda MCP.

**Veredicto:** Es necesario definir los valores por defecto en la implementación de PR4.

---

## 6. Parámetros

### 6.1 Catálogo completo

| Parámetro | Tipo | Spec | Diseño | Stub actual | Obligatorio | Default propuesto |
|---|---|---|---|---|---|---|
| `horas` | `int \| None` | ✅ Opcional | ✅ `int \| None` | ✅ `int \| None = None` | No | `24` (últimas 24h) |
| `tipo` | `str \| None` | ✅ Opcional (lifecycle, tool, error) | ✅ `str \| None` | ✅ `str \| None = None` | No | `None` (todos los tipos) |

### 6.2 Justificación de cada parámetro

#### `horas`
**Qué hace:** Define la ventana temporal hacia atrás desde el momento de la consulta. Ej: `horas=2` → últimos 120 minutos de actividad.

**¿Obligatorio?** No. El spec dice "Opcionales". Si no se especifica, se usa el default (24h propuesto).

**¿Default?** El spec NO especifica un default. La implementación debe definirlo. Se recomienda 24 horas.

**Validación:** Debe ser un entero positivo (≥ 1). Si es 0 o negativo → `ERR_INVALID_ARGUMENT`.

#### `tipo`
**Qué hace:** Filtra eventos por tipo. Acepta valores: `lifecycle`, `tool`, `error`.

**¿Obligatorio?** No. El spec dice "Opcionales". Si no se especifica, se devuelven todos los tipos.

**¿Default?** `None` (todos los tipos).

**Mapeo a `ActivityEvent.type`:** El `ActivityEvent` almacena el tipo como string. Los valores conocidos son `lifecycle`, `tool_invocation`, `error`. El spec usa `tool` (abreviado) mientras que el modelo usa `tool_invocation`. **DISCREPANCIA DETECTADA** (ver §12, C4).

**Validación:** Solo acepta `lifecycle`, `tool`, `error`. Cualquier otro valor → `ERR_INVALID_ARGUMENT`.

### 6.3 Discrepancia spec vs stub

**No hay discrepancia.** Ambos artefactos coinciden: `horas` y `tipo` son opcionales, del mismo tipo.

### 6.4 Parámetros que podrían añadirse pero NO deben

| Parámetro | Riesgo | Motivo |
|---|---|---|
| `fuente` / `source` | Expone módulos internos | Si el usuario filtra por "chronicle" o "vision", está usando nombres de módulo internos. |
| `desde` / `hasta` (ISO 8601) | Complejidad excesiva | `horas` es suficiente para el 95% de casos. Rangos exactos añaden complejidad de validación y parsing. |
| `limite` / `limit` | Microgestión | El límite por defecto (50) es suficiente. Un parámetro `limit` invita a abusos (pedir 10000 eventos). |
| `orden` (asc/desc) | Innecesario | History siempre devuelve descendente (más reciente primero). No hay caso de uso para ascendente. |

---

## 7. Interpretación vs presentación

### 7.1 ¿History SOLO presenta eventos o PUEDE interpretarlos?

**Puede interpretarlos, PERO solo para transformarlos a lenguaje natural. No para extraer significado, patrones o tendencias.**

La transformación permitida:
- Timestamp ISO 8601 → "14:30" (hora legible)
- `type: "tool_invocation"` → "Herramienta de consulta invocada"
- `type: "error"` + `severity: "warning"` + `payload.message` → "Advertencia de rendimiento detectada"
- `source: "vision"` → NO se muestra como "vision". Se omite o se usa término genérico.

La transformación NO permitida:
- Agrupar eventos y derivar conclusiones (ej. "los errores aumentaron" → eso es tendencia, pertenece a progress/insights)
- Priorizar eventos por importancia (eso es recommend)
- Clasificar eventos como "buenos" o "malos" (eso es diagnóstico/health)

### 7.2 Formato de presentación

**Especificado:** Línea de tiempo narrativa en lenguaje natural.
**NO especificado:** Si la narrativa va en `explanation`, `evidence` o un campo nuevo.

**Análisis:** El formato estándar es `evidence` (narrativa en el contenido textual). Pero `EvidenceSource` tiene estructura fija (source, confidence, collected_ago, based_on). Para incluir múltiples entradas narrativas, se requiere una decisión de diseño:

**Opción A** (recomendada): La línea de tiempo completa como texto estructurado dentro de `explanation`. La narrativa se incluye como texto con saltos de línea en `explanation`. `evidence` contiene las fuentes que respaldan la narrativa.

**Opción B**: Crear un nuevo campo `timeline: list[str]` en una subclase `HistoryResponse(ToolResponse)`. Similar a `RecommendResponse` con `priority`. Más limpio pero requiere extensión del modelo.

**Recomendación:** Opción A para PR4 por simplicidad. Si la narrativa crece en complejidad, migrar a Opción B en un Minor futuro.

### 7.3 ¿Puede resumir?

**Hasta dónde:**

| Tipo de resumen | Permitido | Ejemplo | Riesgo |
|---|---|---|---|
| "Hubo 3 errores en la última hora" vs listar cada error | ✅ **Permitido** si hay más de N eventos (ej. >10) | "Se registraron 15 eventos en las últimas 24 horas. 3 fueron errores, 10 tool calls y 2 lifecycle." | Bajo — es un resumen cuantitativo, no interpretativo |
| Resumen por tipo | ✅ **Permitido** como metadato | "Eventos por tipo: 10 tool, 3 error, 2 lifecycle" | Bajo — sigue siendo presentación, no análisis |
| Resumen por módulo | ❌ **NO permitido** | "Vision: 5 eventos, Guardian: 3 eventos" — EXPONE módulos internos | Alto — viola P6 |
| Resumen temporal ("hubo más actividad por la mañana") | ❌ **NO permitido** | "La mayoría de los eventos ocurrieron entre las 9 y las 12" — es patrón/tendencia | Alto — invade insights/progress |
| Tendencia ("los errores están aumentando") | ❌ **NO permitido** | "En la última hora hay más errores que en las anteriores" — es tendencia | Alto — invade progress |

**Regla de oro:** History puede CONTAR eventos pero no INTERPRETARLOS. Contar es "3 errores". Interpretar es "los errores están aumentando".

---

## 8. Resumen de eventos

### 8.1 Límites explícitos

| Tipo de resumen | Permitido | Condición | Formato |
|---|---|---|---|
| **Resumen por tipo** | ✅ Sí | Siempre, como metadato adicional en summary/explanation | "3 eventos de tipo error, 10 tool calls, 2 lifecycle" |
| **Resumen por módulo** | ❌ No | Nunca — expone módulos internos | — |
| **Resumen temporal (counts por hora/día)** | ✅ Parcial | Solo conteos planos, sin interpretación de tendencia | "Eventos por hora: 14:00 (5), 15:00 (3), 16:00 (7)" |
| **Tendencia** | ❌ No | Nunca — pertenece a progress | — |
| **Resumen por severidad** | ✅ Sí | Siempre, como metadato adicional | "2 warnings, 1 error, 12 info" |

### 8.2 Regla exacta

History puede resumir eventos por sus propiedades **directas** (type, severity, timestamp). NO puede resumir por propiedades **derivadas** (tendencia, patrones, correlaciones).

La línea: **propiedad directa = está en el evento. Propiedad derivada = requiere cruzar múltiples eventos o aplicar lógica de negocio.**

---

## 9. Comportamiento sin historial

### 9.1 Sin eventos en el período consultado

**Respuesta:** "No hay actividad registrada en el período solicitado."

**Confidence:** LOW (0.25–0.49) — los datos existen pero el resultado es negativo. El spec §Scenario "Sin actividad en el período" dice explícitamente "Confidence MUST ser LOW (dato negativo)".

**Código:** No es error. Es respuesta exitosa con datos vacíos. Se devuelve como `ToolResponse` normal, NO como error.

**Evidence:** Chronicle está presente y respondió, pero devolvió 0 eventos. Se incluye `EvidenceSource` para Chronicle con `based_on = "0 eventos en el período consultado"`.

**Ejemplo de respuesta:**
```json
{
  "summary": "No hay actividad registrada en las últimas 24 horas",
  "explanation": "El período entre 2026-07-15 14:00 y 2026-07-16 14:00 no contiene eventos registrados.",
  "evidence": [
    {
      "source": "Chronicle",
      "confidence": 0.8,
      "collected_ago": 0,
      "based_on": "0 eventos en el período consultado"
    }
  ],
  "confidence": 0.3,
  "generated_at": "2026-07-16T14:00:00+00:00",
  "data_freshness": 0
}
```

### 9.2 Chronicle no responde (timeout, error, o None en ServiceRegistry)

**Respuesta:** Error `ERR_DEPENDENCY_UNAVAILABLE`.

**Mensaje:** "No se pudo obtener el historial de actividad. El módulo de registro de eventos no está disponible."

**Comportamiento:** Chronicle es REQUERIDO. Si no responde, history no puede funcionar. Esto es por diseño (ADR-001: "Chronicle timeout → ERR_DEPENDENCY_UNAVAILABLE").

**Confidence:** LOW (0.0–0.24). Sin datos de la fuente principal, no hay confianza.

**Código:** `ERR_DEPENDENCY_UNAVAILABLE` (del catálogo global de errores).

### 9.3 Filtros no matchean nada

**Caso 1: `tipo=error` pero no hay errores en el período.**

Respuesta: "No hay actividad registrada en el período solicitado." (mismo que §9.1). No es necesario mencionar el filtro específico; el mensaje genérico cubre el caso. Opcionalmente: "No se encontraron eventos de tipo 'error' en el período solicitado."

**Caso 2: `horas=1` pero no hay eventos en la última hora.**

Respuesta: "No hay actividad registrada en la última hora." (idem).

**Caso 3: `horas=168` (1 semana) y no hay eventos.**

Respuesta: "No hay actividad registrada en los últimos 7 días." (idem, con mención del período).

**Regla:** No se devuelve error por filtros sin resultados. Se devuelve respuesta exitosa con datos vacíos y confidence LOW.

### 9.4 Vision opcional no disponible

**Comportamiento:** History funciona solo con Chronicle. La narrativa se construye exclusivamente con datos de Chronicle. La confidence se calcula solo con Chronicle disponible.

### 9.5 Ambos módulos fallan (Chronicle + Vision)

**Respuesta:** Error `ERR_DEPENDENCY_UNAVAILABLE` (Chronicle es requerido y falló; Vision no puede suplirlo).

**Mensaje:** "No se pudo obtener el historial de actividad. El módulo de registro de eventos no está disponible."

### 9.6 Mensajes exactos definidos

| Escenario | Mensaje exacto |
|---|---|
| Sin eventos en el período | `"No hay actividad registrada en el período solicitado."` |
| Sin eventos (con `horas` específico) | `"No hay actividad registrada en las últimas N horas."` |
| Sin eventos (con `tipo` específico) | `"No se encontraron eventos de tipo '{tipo}' en el período solicitado."` |
| Chronicle no disponible | `"No se pudo obtener el historial de actividad. El módulo de registro de eventos no está disponible."` |
| `horas` inválido (≤ 0) | `"El parámetro 'horas' debe ser un número entero positivo."` |
| `tipo` inválido | `"El parámetro 'tipo' debe ser uno de: lifecycle, tool, error."` |

---

## 10. Confidence

### 10.1 Cálculo

El cálculo de confidence sigue ADR-003: promedio ponderado de módulos disponibles vs. consultados.

Para history específicamente:

```python
n_expected = 2  # Chronicle (obligatorio) + Vision (opcional)
n_available = sum(1 for v in results.values() if v is not None)
confidence = round(n_available / n_expected, 2)
```

### 10.2 Factores que afectan

| Factor | Efecto en confidence |
|---|---|
| Chronicle responde | Base. Sin Chronicle, no hay history → error. |
| Vision responde (opcional) | Aumenta a 1.0 si está disponible. |
| Chronicle responde con 0 eventos | Confidence baja a LOW (~0.30). El spec §Scenario "Sin actividad en el período" dice explícitamente "Confidence MUST ser LOW (dato negativo)". |
| Chronicle responde con datos | Confidence HIGH (≥0.75). |
| Chronicle timeout | Error `ERR_DEPENDENCY_UNAVAILABLE` (no hay confidence porque no hay respuesta). |
| Vision timeout | No afecta; Vision es opcional. Confidence se calcula solo con Chronicle. |

### 10.3 Tabla de escenarios con valores resultantes

| Escenario | Chronicle | Vision | Events | Confidence | Código |
|---|---|---|---|---|---|
| **Happy path completo** | ✅ responde | ✅ responde | ≥1 | 1.00 (VERY_HIGH) | — |
| **Happy path solo Chronicle** | ✅ responde | ❌ timeout/None | ≥1 | 0.50 (MEDIUM) | — |
| **Sin eventos (completo)** | ✅ responde | ✅ responde | 0 | **0.30 (LOW)** — spec explícito | — |
| **Sin eventos (solo Chronicle)** | ✅ responde | ❌ timeout/None | 0 | **0.25 (LOW)** — dato negativo + parcial | — |
| **Muchos eventos (+50)** | ✅ responde | variable | ≥50 | Según disponibilidad de Vision | — |
| **Chronicle timeout** | ❌ timeout | variable | — | 0.0 | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Chronicle None** | ❌ None | variable | — | 0.0 | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Chronicle + Vision timeout** | ❌ timeout | ❌ timeout | — | 0.0 | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Vision enrich + Chronicle ok** | ✅ responde | ✅ responde | ≥1 | 1.00 (VERY_HIGH) | — |
| **`horas` inválido** | No consultado | No consultado | — | 0.0 | `ERR_INVALID_ARGUMENT` |
| **`tipo` inválido** | No consultado | No consultado | — | 0.0 | `ERR_INVALID_ARGUMENT` |

### 10.4 NOTA IMPORTANTE sobre confidence en escenario "sin eventos"

El spec §Scenario: "Sin actividad en el período" dice:

> THEN la respuesta MUST indicar "No hay actividad registrada en el período solicitado"
> AND Confidence MUST ser LOW (dato negativo)

Esto es EXPLÍCITO y debe respetarse. La confidence NO puede ser HIGH aunque los datos sean confiables, porque el resultado es negativo. La lógica es: "estoy seguro de que no hay datos" ≠ "tengo alta confianza en un resultado positivo".

**Sin embargo**, esto crea una tensión: si el usuario pregunta por un período sin actividad, recibe confidence LOW, lo que podría interpretarse como "el sistema no está seguro". Es un comportamiento intencional del spec, pero debe documentarse para que los consumidores de la API lo entiendan.

---

## 11. EvidenceSources

### 11.1 Módulos que aparecen en evidence

| Módulo | ¿Aparece en evidence? | Condición | Campo `source` |
|---|---|---|---|
| **Chronicle** | ✅ Siempre (si responde) | Siempre que Chronicle responda dentro del timeout | `"Chronicle"` |
| **Vision** | ✅ Opcional | Solo si Vision responde dentro del timeout | `"Vision"` |

### 11.2 Campos de cada EvidenceSource

**Chronicle** (cuando responde):
```json
{
  "source": "Chronicle",
  "confidence": 0.8,
  "collected_ago": 0,
  "based_on": "12 eventos en las últimas 24 horas"
}
```

**Vision** (cuando responde):
```json
{
  "source": "Vision",
  "confidence": 0.8,
  "collected_ago": 0,
  "based_on": "logs del sistema"
}
```

### 11.3 Notas sobre evidence

- El `source` "Chronicle" y "Vision" son identificadores técnicos internos de la API, no texto visible al usuario en la respuesta narrativa (ver §1.4 del spec sobre status: los nombres en `evidence[].source` son aceptables).
- `based_on` para Chronicle debe reflejar el resultado de la consulta: cantidad de eventos, rango temporal.
- `confidence` individual de cada EvidenceSource se establece en 0.8 por defecto (dato disponible, fuente confiable). Si un módulo devuelve 0 eventos, su evidence confidence sigue siendo 0.8 (el módulo funcionó correctamente, simplemente no hay datos).

---

## 12. Contradicciones entre artefactos

### 12.1 Mapa de contradicciones detectadas

| # | Artefactos en conflicto | Descripción | Severidad | Resolución |
|---|---|---|---|---|
| **C1** | Spec §Scenario vs P6 | El ejemplo en §Scenario muestra "Módulo Vision iniciado". P6 dice "ninguna tool revela Vision, Chronicle, etc." El ejemplo viola P6. | **CRITICAL** | El ejemplo de "Módulo Vision iniciado" viola P6. History debe usar lenguaje neutral: "Sistema de monitoreo iniciado" o "Componente principal iniciado". NO debe decir "Módulo Vision". |
| **C2** | Spec vs Design: código de error | El spec §Catálogo Global de Errores — Cobertura muestra `ERR_NO_DATA` para history. El diseño (ADR-001 docstring) dice "Chronicle timeout → ERR_DEPENDENCY_UNAVAILABLE". | **WARNING** | Ambos son correctos pero para condiciones distintas: `ERR_NO_DATA` cuando Chronicle responde con 0 eventos; `ERR_DEPENDENCY_UNAVAILABLE` cuando Chronicle no responde. La implementación debe manejar ambos. |
| **C3** | Proposal vs Spec: chronicle_stats | Proposal §"chronicle_stats → (fusionada en history)". Pero el spec de history NO menciona stats en ningún lado. | **WARNING** | La fusión de `chronicle_stats` en history no está especificada en el spec. Si history no incluye stats, ¿dónde quedan? ¿Hay una herramienta Advanced `chronicle_stats` separada? Esto debe resolverse en el spec. |
| **C4** | Spec vs Modelo de datos: tipo de evento | Spec dice `tipo` acepta "lifecycle, tool, error". `ActivityEvent.type` usa "tool_invocation" (no "tool"). | **WARNING** | El filtro `tipo=tool` debe mapearse a `EventFilter.type = "tool_invocation"`. Esto debe documentarse en la implementación. Si no se mapea, el filtro no funcionará. |
| **C5** | Spec vs Design: default de `horas` | El spec no define default para `horas` cuando se omite. El diseño no lo define. Chronicle subyacente devuelve hasta 100 eventos sin ventana temporal. | **CRITICAL** | Definir constantes `HISTORY_DEFAULT_HOURS`, `HISTORY_DEFAULT_LIMIT`, `HISTORY_MAX_LIMIT` en coordinator.py. Ver §5.3. |
| **C6** | Spec §Anti-Patterns vs Spec §Scenario | Anti-patterns: "No debe requerir filtros". Scenario "Happy path — actividad registrada": "WHEN un agente llama `apoch_history`" (sin filtros). Consistente. | **NINGUNA** | Sin contradicción. History funciona sin filtros usando valores por defecto. |
| **C7** | Spec: Formato de narrativa vs ToolResponse | El spec requiere "línea de tiempo cronológica en lenguaje natural" pero ToolResponse no tiene un campo `timeline`. EvidenceSource tampoco tiene estructura para múltiples entradas narrativas. | **INFO** | Decisión de implementación: usar `explanation` para la narrativa completa (texto con saltos de línea) o extender ToolResponse. Se recomienda la primera opción para PR4. |
| **C8** | Design vs Spec: Vision como módulo | Design §Internal Mapping: "Chronicle, Vision". Spec §1.7: "Chronicle (events), Vision (logs para enriquecer narrativa)". Ambos coinciden en que Vision es opcional. | **NINGUNA** | Sin contradicción. Vision es opcional en ambos. |
| **C9** | Spec: "nombres de módulo internos" prohibido vs ejemplo con "Vision" | §1.4 (Prohibido) dice indirectamente que los nombres de módulo internos no se revelan. Pero el ejemplo narrativo usa "Módulo Vision". | **CRITICAL** | Misma raíz que C1. Resolver eliminando nombres de módulo de la narrativa. |
| **C10** | Tasks vs Spec: Acceptance Gate | Tasks §4.2: "ninguna devuelve ERR_NOT_IMPLEMENTED". Pero el stub actual de `history()` SÍ devuelve `ERR_NOT_IMPLEMENTED`. | **NINGUNA** | Es correcto porque history aún no está registrada. Al registrarla en PR4, debe implementarse completamente y nunca devolver `ERR_NOT_IMPLEMENTED`. |

### 12.2 Resumen de contradicciones por severidad

| Severidad | Cantidad | IDs |
|---|---|---|
| **CRITICAL** | 3 | C1, C5, C9 |
| **WARNING** | 3 | C2, C3, C4 |
| **INFO** | 1 | C7 |
| **NINGUNA** | 3 | C6, C8, C10 |

---

## 13. Zonas grises

### 13.1 Catálogo de zonas grises

| # | Zona gris | Descripción | Severidad | Resolución |
|---|---|---|---|---|
| **ZG1** | Nombres de módulo en narrativa | El spec ejemplo usa "Módulo Vision" pero P6 prohíbe exponer módulos internos. ¿Cómo referirse al componente sin usar su nombre interno? | **CRITICAL** | Usar términos genéricos: "Sistema de monitoreo", "Componente de registro", "Sistema de ejecución". O eliminar la referencia al módulo por completo: "14:30 — Error: conexión perdida". |
| **ZG2** | Default de `horas` sin definir | El spec no define qué pasa si se omite `horas`. Chronicle devuelve hasta 100 eventos sin filtro temporal. | **CRITICAL** | Definir constantes: `HISTORY_DEFAULT_HOURS=24`, `HISTORY_DEFAULT_LIMIT=50` (ver §5.3). |
| **ZG3** | Límite de eventos de history | ¿Cuántos eventos puede devolver history? ¿Hay un máximo? El spec no lo dice. Sin límite, podría devolver miles de eventos y saturar la respuesta MCP. | **CRITICAL** | Definir `HISTORY_DEFAULT_LIMIT=50` y `HISTORY_MAX_LIMIT=200` (ver §5.3). |
| **ZG4** | "chronicle_stats fusionada en history" | Proposal dice que stats se fusiona en history, pero el spec no menciona stats. ¿Qué significa exactamente "fusionada"? | **WARNING** | History PUEDE incluir conteos por tipo como metadato en summary/explanation, pero NO debe incluir `EventStats` completo (total, by_type, by_severity) porque eso sería crudo. |
| **ZG5** | Mapeo `tipo` → `EventFilter.type` | El spec usa "tool" pero `ActivityEvent.type` usa "tool_invocation". Si no se mapea, `tipo=tool` no devuelve nada. | **WARNING** | Mapear `"tool"` → `"tool_invocation"` en la implementación. Documentar en código. |
| **ZG6** | Confidence LOW en dato negativo | El spec exige confidence LOW cuando no hay eventos. Esto puede confundir a clientes MCP que interpreten confidence baja como "poca confiabilidad del sistema" en vez de "dato negativo confiable". | **INFO** | Documentar en la especificación técnica que confidence baja en history indica ausencia de datos, no poca confiabilidad. |
| **ZG7** | Vision como "logs para enriquecer narrativa" | ¿Qué método exacto de Vision se consulta? ¿`VisionModule.logs()`? ¿`VisionModule.module_state()`? El spec no lo especifica. | **WARNING** | **Recomendación: NO consultar Vision en PR4.** Dejar esa dependencia para un Minor futuro. History funciona completo solo con Chronicle. Esto reduce complejidad y riesgo de invasión de `apoch_logs`. |
| **ZG8** | ¿History resume por módulo? | El resumen por tipo está permitido. ¿El resumen por `source`? El `ActivityEvent` tiene `source` (nombre del módulo). Si history resume por `source`, estaría exponiendo módulos internos. | **WARNING** | History NO debe resumir ni agrupar por `source`. Eso expone arquitectura interna. Si el usuario necesita saber qué módulo generó cada evento, la narrativa puede incluir el tipo de componente (ej. "módulo de monitoreo") pero no el nombre interno. |

### 13.2 Zonas grises similares a PR2 (status review)

El boundary review de status identificó estas zonas grises. Verificar si history tiene las mismas:

| Zona gris de PR2 | ¿Aplica a history? | Estado |
|---|---|---|
| Confidence "siempre HIGH" vs degradación | Parcial. History tiene confidence variable según datos disponibles. El spec ya contempla LOW para datos negativos. | **RESUELTA** en spec. Sin ambigüedad. |
| Oracle opcional vs parte del contrato | No aplica (Oracle no es módulo de history). | **N/A** |
| Actividad reciente no definida | **SÍ APLICA.** Los límites de history (horas default, limit default, max limit) no están definidos. | **CRÍTICO** — resolver en PR4. |
| EvidenceSource con nombres de módulo | **SÍ APLICA.** Chronicle y Vision aparecen como source en evidence. El spec permite esto solo en el campo técnico `evidence[].source`. | **ACEPTABLE** siguiendo el mismo criterio que status. |

### 13.3 Veredicto de zona gris

| Severidad | Cantidad | IDs |
|---|---|---|
| CRITICAL | 3 | ZG1, ZG2, ZG3 |
| WARNING | 4 | ZG4, ZG5, ZG7, ZG8 |
| INFO | 1 | ZG6 |

**Tres zonas grises CRITICAL que deben resolverse ANTES de PR4.**

---

## 14. Future Creep

### 14.1 Riesgos de crecimiento incorrecto

| # | Riesgo | Síntoma | Herramienta invadida |
|---|---|---|---|
| 1 | Añadir parámetro `fuente`/`source` | History permite filtrar por módulo interno | Expone implementación (P6) |
| 2 | Añadir `desde`/`hasta` (ISO 8601) | History acepta rangos exactos en vez de `horas` relativo | Complejidad innecesaria |
| 3 | Añadir `limite` configurable | History permite pedir 10000 eventos | Abuso de API, performance |
| 4 | Añadir agrupación por tipo como feature principal | History empieza a estructurarse en secciones por tipo de evento | `progress` / `insights` |
| 5 | Añadir "eventos importantes" o "eventos destacados" | History filtra/prioriza eventos por "importancia" | `recommend` |
| 6 | Añadir búsqueda full-text en eventos | History permite buscar texto en payloads | Complejidad excesiva, exposición de datos internos |
| 7 | Añadir gráficos o tendencias visuales | History incluye "los errores aumentaron un 20%" | `progress` / `insights` |
| 8 | Añadir "causa de eventos" | History dice "el error X ocurrió porque Y" | `health` (diagnóstico causal) |
| 9 | Añadir exportación (CSV, JSON) | History tiene modo "exportar eventos" | Violación P4 (acción), además expone datos crudos |
| 10 | Añadir correlación entre eventos | History conecta eventos en secuencias causales | `insights` (patrones) |
| 11 | Añadir anotaciones de usuario | History permite al usuario etiquetar/comentar eventos | Mutación de estado (violación P4) |
| 12 | Añadir replay/línea de tiempo animada | History se convierte en un reproductor de eventos | Expansión de dominio no prevista |

### 14.2 Reglas para impedir el crecimiento incorrecto

#### Regla 1: Sin parámetros que expongan implementación
`apoch_history` no acepta `source`, `module` ni ningún filtro que requiera conocimiento de la arquitectura interna. Los únicos filtros son `horas` (tiempo) y `tipo` (categoría de evento del usuario, no nombre de módulo).

#### Regla 2: Sin interpretación causal
History muestra eventos en orden cronológico. No explica por qué ocurrieron, no los conecta en secuencias causales, no sugiere qué hacer con ellos.

#### Regla 3: Sin tendencias ni patrones
History cuenta eventos, no los interpreta. "3 errores" es contar. "Los errores están aumentando" es interpretar. History nunca cruza la línea de contar a interpretar.

#### Regla 4: Sin exposición de datos crudos
Los eventos se transforman a narrativa. Nunca se exponen como JSON, dicts, o estructuras de datos. El `ActivityEvent.payload` nunca es visible.

#### Regla 5: Sin acción sobre eventos
History es consulta pura. No permite responder a eventos, marcarlos como leídos, ni ejecutar acciones basadas en ellos.

#### Regla 6: Narrativa siempre, datos nunca
La línea de tiempo SIEMPRE es texto en lenguaje natural. Nunca se devuelven objetos estructurados que representen eventos individuales.

#### Regla 7: Latencia máxima como límite de crecimiento
Tiempo objetivo: < 1 segundo. Cualquier añadido que empuje la latencia por encima de 1s requiere optimización o exclusión.

#### Regla 8: El nombre "history" es el ancla
La pregunta "¿Un usuario entendería esto como 'historial de actividad del sistema'?" es el test de fuego. Si la respuesta es dudosa, no pertenece a history.

---

## 15. Definition of Done específica para PR4

### 15.1 Requisitos funcionales

- [ ] **15.1.1** `ApochCoordinator.history()` implementado consultando Chronicle (obligatorio) y Vision (opcional) via `ServiceRegistry`.
- [ ] **15.1.2** La respuesta incluye **siempre**: `api_version`, `summary`, `explanation`, `evidence`, `confidence`, `generated_at`, `data_freshness`.
- [ ] **15.1.3** La respuesta incluye una **línea de tiempo cronológica descendente** (más reciente primero) en lenguaje natural.
- [ ] **15.1.4** Cada entrada de la línea de tiempo es una **frase narrativa** (ej: "14:30 — Error: conexión perdida con el servicio de base de datos").
- [ ] **15.1.5** El parámetro `horas` (opcional) filtra eventos a las últimas N horas. Si se omite, se usa `HISTORY_DEFAULT_HOURS = 24`.
- [ ] **15.1.6** El parámetro `tipo` (opcional) filtra eventos por tipo. Acepta: `lifecycle`, `tool`, `error`. Si se omite, se devuelven todos los tipos.
- [ ] **15.1.7** El filtro `tipo=tool` se mapea correctamente a `EventFilter.type = "tool_invocation"` (resuelve C4).
- [ ] **15.1.8** Si se llama sin parámetros, se usan los valores por defecto: `horas=24`, sin filtro de tipo.
- [ ] **15.1.9** Si no hay eventos en el período solicitado → "No hay actividad registrada en el período solicitado." con confidence LOW.
- [ ] **15.1.10** Si `horas` es inválido (≤ 0 o no entero) → `ERR_INVALID_ARGUMENT`.
- [ ] **15.1.11** Si `tipo` no es uno de los valores aceptados → `ERR_INVALID_ARGUMENT`.
- [ ] **15.1.12** Si Chronicle no responde (timeout, error, o None) → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **15.1.13** Si Chronicle responde pero Vision no → history funciona solo con Chronicle.
- [ ] **15.1.14** La línea de tiempo **NUNCA** incluye: IDs de evento, SQL, `event_type`, `source`, `severity`, `payload`, tracebacks, nombres de módulo internos en texto narrativo.
- [ ] **15.1.15** La respuesta **NUNCA** incluye: diagnóstico, recomendaciones, productividad, patrones, logs técnicos, estado actual, módulos consultados, orden de ejecución.
- [ ] **15.1.16** La respuesta puede incluir un **resumen cuantitativo** (conteo por tipo) en `summary` o `explanation`, pero no interpretación ni tendencias.
- [ ] **15.1.17** La `suggested_action` es `None` para history (es consulta pura, no hay acción sugerida del historial). Esto es una diferencia con otras tools.

### 15.2 Requisitos técnicos

- [ ] **15.2.1** Definir constantes en coordinator.py:
  - `HISTORY_DEFAULT_HOURS: int = 24`
  - `HISTORY_DEFAULT_LIMIT: int = 50`
  - `HISTORY_MAX_LIMIT: int = 200`
- [ ] **15.2.2** History usa `_query_modules()` con timeouts individuales: Chronicle (0.5s), Vision (0.5s).
- [ ] **15.2.3** Las consultas a módulos se ejecutan en paralelo con `asyncio.gather(return_exceptions=True)` (ADR-007).
- [ ] **15.2.4** Timeouts y excepciones de módulos se capturan: el módulo se marca como no disponible, la respuesta continúa (ADR-004).
- [ ] **15.2.5** Si Chronicle no responde (timeout, excepción, o None en ServiceRegistry) → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **15.2.6** Confidence se calcula como promedio de módulos disponibles vs. consultados:
  - Chronicle + Vision responden → 1.00 (VERY_HIGH)
  - Solo Chronicle responde → 0.50 (MEDIUM)
  - Chronicle responde con 0 eventos → **0.30 (LOW)** — ver §10.4
  - Chronicle no responde → error (confidence no aplica)
- [ ] **15.2.7** `api_version` se establece desde la constante en `version.py` (ADR-005).
- [ ] **15.2.8** `generated_at` usa ISO 8601 con UTC.
- [ ] **15.2.9** `data_freshness` refleja la antigüedad de los datos más antiguos entre los módulos que respondieron.
- [ ] **15.2.10** `evidence` contiene una entrada por cada módulo que respondió, con source, confidence, collected_ago, based_on.
- [ ] **15.2.11** No se importa ningún módulo concreto (ChronicleModule, VisionModule, etc.) en coordinator.py. Solo duck-typing via ServiceRegistry.
- [ ] **15.2.12** La línea de tiempo narrativa se incluye en `explanation` o como texto estructurado, no como lista de objetos.
- [ ] **15.2.13** `suggested_action` se omite (None) o se establece como string vacío. History no produce acciones sugeridas.

### 15.3 Requisitos de pruebas

- [ ] **15.3.1** Test: Happy path — Chronicle devuelve eventos → narrativa cronológica con HIGH confidence (≥0.75).
- [ ] **15.3.2** Test: Happy path con Vision — ambos módulos responden → narrativa enriquecida con VERY_HIGH confidence (1.00).
- [ ] **15.3.3** Test: Sin actividad — Chronicle responde con 0 eventos → "No hay actividad registrada en el período solicitado." con LOW confidence.
- [ ] **15.3.4** Test: Filtro por horas — `horas=2` → solo eventos de las últimas 2 horas.
- [ ] **15.3.5** Test: Filtro por tipo — `tipo=error` → solo eventos de tipo error.
- [ ] **15.3.6** Test: Filtro combinado — `horas=24, tipo=lifecycle` → solo eventos lifecycle de las últimas 24h.
- [ ] **15.3.7** Test: Sin parámetros → usa defaults (24h, 50 eventos máximo, todos los tipos).
- [ ] **15.3.8** Test: Chronicle timeout → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **15.3.9** Test: Chronicle no disponible (None) → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **15.3.10** Test: Vision timeout → history funciona con Chronicle solamente, confidence MEDIUM (0.50).
- [ ] **15.3.11** Test: Vision no disponible (None) → history funciona con Chronicle solamente.
- [ ] **15.3.12** Test: `horas` inválido (0, -1) → `ERR_INVALID_ARGUMENT`.
- [ ] **15.3.13** Test: `tipo` inválido ("debug") → `ERR_INVALID_ARGUMENT`.
- [ ] **15.3.14** Test: `tipo=tool` se mapea correctamente a `tool_invocation` en el filtro de Chronicle.
- [ ] **15.3.15** Test: La respuesta no contiene campos prohibidos (IDs, SQL, tracebacks, event_type crudo, source crudo, payload).
- [ ] **15.3.16** Test: La línea de tiempo usa lenguaje natural (no JSON, no dicts, no objetos estructurados).
- [ ] **15.3.17** Test: La narrativa no contiene nombres de módulo internos ("Vision", "Chronicle", "Guardian") como texto visible.
- [ ] **15.3.18** Test: El formato de respuesta coincide con ToolResponse esperado.
- [ ] **15.3.19** Test: `api_version = "1.0"` en la respuesta.
- [ ] **15.3.20** Test: `suggested_action` es None o está ausente en la respuesta.
- [ ] **15.3.21** Test: Con más de 50 eventos en el período, la respuesta se limita a 50 eventos.
- [ ] **15.3.22** Test: `chronicle_stats` NO está presente en la respuesta (resuelve C3 — stats no deben exponerse crudos).

### 15.4 Requisitos de UX

- [ ] **15.4.1** Un usuario nuevo entiende qué hace `apoch_history` solo con el nombre y la descripción en ≤30 segundos (P8 — Rule of 30 Seconds).
- [ ] **15.4.2** La respuesta es autosuficiente — no requiere llamar a otra herramienta para entenderla (P5).
- [ ] **15.4.3** `summary` es una sola línea que responde la pregunta "¿qué pasó?" (ej: "12 eventos registrados en las últimas 24 horas").
- [ ] **15.4.4** `explanation` proporciona la línea de tiempo en lenguaje natural sin jerga técnica.
- [ ] **15.4.5** La respuesta usa lenguaje natural, no estructuras de datos internas.
- [ ] **15.4.6** Los tiempos se muestran en formato legible ("14:30", no "2026-07-16T14:30:00+00:00").
- [ ] **15.4.7** Los tipos de evento se muestran en lenguaje natural ("error", no "tool_invocation").
- [ ] **15.4.8** La línea de tiempo es descendente (el evento más reciente primero).

### 15.5 Requisitos de arquitectura

- [ ] **15.5.1** `ApochCoordinator.history()` no tiene estado — cada llamada es independiente.
- [ ] **15.5.2** History no depende del orden de ejecución de módulos (ADR-007).
- [ ] **15.5.3** History sobrevive a la eliminación de Vision (módulo opcional). NO sobrevive a la eliminación de Chronicle (es su propósito).
- [ ] **15.5.4** Si mañana se reemplazan Chronicle o Vision por implementaciones diferentes, `apoch_history` no cambia (P7 — Intent Stability Rule).
- [ ] **15.5.5** No se registran otras herramientas públicas nuevas en este PR (registro progresivo, P10).
- [ ] **15.5.6** Ninguna herramienta existente (status, health) se ve afectada por este PR.
- [ ] **15.5.7** La herramienta respeta el presupuesto de PR4 en `tasks.md`: ≤400 LOC netas, ≤15 archivos modificados.
- [ ] **15.5.8** La implementación usa duck-typing vía ServiceRegistry. No importa ChronicleModule ni VisionModule directamente.

### 15.6 Acceptance Gate (de tasks.md §4.2)

- [ ] **15.6.1** `apoch_history` es visible en `tools/list`.
- [ ] **15.6.2** Ninguna tool futura (recommend, progress, insights, logs) es visible en `tools/list`.
- [ ] **15.6.3** Ninguna herramienta pública devuelve `ERR_NOT_IMPLEMENTED` (solo status, health y history implementados; el resto no están registradas).
- [ ] **15.6.4** Ruff: `ruff check src/apoch/` pasa sin errores nuevos.
- [ ] **15.6.5** Pytest: `pytest tests/public_api/test_history.py -v` pasa completo.
- [ ] **15.6.6** Tipado: `mypy src/apoch/` pasa sin errores nuevos.

---

## Apéndice A: Mapa de decisiones ADR pertinentes

| Decisión | Referencia | Impacto en history |
|---|---|---|
| ServiceRegistry tipado | ADR-001 | History recibe servicios con tipo conocido, sin riesgos de string keys |
| ToolResponse unificado | ADR-002 | History devuelve el mismo formato que todas las tools |
| Evidence + Confidence | ADR-003 | History muestra qué módulos respondieron y con qué confianza |
| Timeout por módulo | ADR-004 | History nunca crashea por módulo lento; degrada gracefulmente |
| API versionado | ADR-005 | History incluye `api_version` para detección de cambios |
| Backward compatibility | ADR-006 | `chronicle_query` será alias de `apoch_history` en PR9 |
| Concurrencia async | ADR-007 | History consulta módulos en paralelo con timeouts individuales |
| Parámetros opcionales (horas, tipo) | Spec §1.4 | History acepta filtros opcionales |
| Public Visibility Rule | ADR-001 §Política | History solo se registra cuando está completo (PR4) |
| Intent Stability Rule | P7 | History sobrevive a cambios de implementación de Chronicle y Vision |
| Chronicle como REQUERIDO | ADR-001 history docstring | History depende de Chronicle para su propósito. Sin Chronicle, no hay historial. |
| Vision como OPCIONAL | ADR-001 history docstring | Vision enriquece pero no define. History funciona sin Vision. |
| Narrativa, no datos crudos | Spec §1.4 + §1.9 | History transforma eventos a lenguaje natural. Nunca expone JSON de eventos. |
| Sin nombres de módulo internos | P6 | History no revela Vision, Chronicle, Guardian, etc. en texto narrativo. |

---

## Apéndice B: Tensiones detectadas

| # | Tensión | Descripción | Severidad | Recomendación |
|---|---|---|---|---|
| T1 | Nombres de módulo en narrativa vs P6 | El spec ejemplo usa "Módulo Vision iniciado" pero P6 prohíbe revelar módulos internos. | **CRITICAL** | Eliminar nombres de módulo de la narrativa. Usar términos genéricos. Cambiar el ejemplo en el spec. |
| T2 | Default de `horas` y límite de eventos no definidos | Spec no dice qué pasa si se omite `horas`. Chronicle default limit=100. Sin límite superior definido. | **CRITICAL** | Definir `HISTORY_DEFAULT_HOURS=24`, `HISTORY_DEFAULT_LIMIT=50`, `HISTORY_MAX_LIMIT=200` en coordinator.py y spec. |
| T3 | chronicle_stats fusionada pero no especificada | Proposal dice que stats se fusiona en history, pero spec no lo implementa. | **WARNING** | Decidir: (a) history incluye conteos agregados en summary/explanation, o (b) stats se queda como Advanced separada. Se recomienda (a) limitado. |
| T4 | Mapeo `tipo=tool` → `tool_invocation` | Spec usa "tool" pero modelo usa "tool_invocation". Sin mapeo explícito, el filtro no funciona. | **WARNING** | Implementar mapeo en history(). Documentar en código. |
| T5 | Vision como módulo opcional no especificado | ¿Qué método de Vision se consulta? ¿ModuleState? ¿Logs? ¿Ambos? | **WARNING** | **Recomendación: NO incluir Vision en PR4.** Dejar esa dependencia para un Minor futuro. History funciona completo solo con Chronicle. Esto reduce complejidad y riesgo de invasión de `apoch_logs`. |
| T6 | Confidence LOW en "sin eventos" puede confundir | El spec exige confidence LOW cuando no hay eventos, pero los datos son confiables (Chronicle respondió). | **INFO** | Documentar en la API que confidence baja en history indica ausencia de datos, no poca confiabilidad. |
| T7 | suggested_action en history | Todas las tools tienen `suggested_action`. History no tiene acción sugerida porque solo muestra el pasado. | **INFO** | History debe devolver `suggested_action = None`. El campo debe estar presente pero vacío, o omitirse. Es la ÚNICA tool que no produce acción. |
| T8 | Extensión de ToolResponse para narrativa | La línea de tiempo narrativa no encaja naturalmente en `evidence` (estructura fija) ni en `explanation` (texto plano). | **INFO** | Usar `explanation` para la narrativa completa con saltos de línea. Si en el futuro se necesita estructura más rica, crear `HistoryResponse(ToolResponse)` con un campo `timeline`. |
| T9 | Límite de eventos vs narrativa completa | Si hay 50 eventos, la narrativa en `explanation` puede ser muy larga. | **INFO** | El límite de 50 eventos mantiene la respuesta manejable. Si hay más de 50, indicar en summary: "50+ eventos registrados. Use filtros para acotar la búsqueda." |
| T10 | chronicle_query como alias en PR9 | La tool legacy `chronicle_query` acepta `source`, `event_type`, `since`, `until`, `limit`. Al convertirla en alias de history, se pierden filtros (`source` expone módulos). | **WARNING** | El alias debe mapear: `event_type` → `tipo`, `since` → calcular `horas` desde el timestamp. `source` y `until` no tienen equivalente → documentar que se ignoran o devolver error. Esto debe planificarse en PR9, no en PR4. |

---

## Veredicto final: PR4 HALT — Cambios necesarios antes de comenzar

**PR4 NO PUEDE COMENZAR** hasta que se resuelvan los siguientes cambios:

### Cambios obligatorios (bloqueantes)

| # | Acción | Archivo | Detalle |
|---|---|---|---|
| **B1** | Definir constantes de límites | `src/apoch/public_api/coordinator.py` | Añadir `HISTORY_DEFAULT_HOURS = 24`, `HISTORY_DEFAULT_LIMIT = 50`, `HISTORY_MAX_LIMIT = 200` |
| **B2** | Corregir ejemplo narrativo en spec | `openspec/changes/mcp-tools-redesign/specs/mcp-public-api/spec.md` | Reemplazar "09:15 — Módulo Vision iniciado" por "09:15 — Sistema de monitoreo iniciado" (sin nombres de módulo internos). Aplica a §Scenario y §Anti-Patterns. |
| **B3** | Añadir sección de límites en spec | `openspec/changes/mcp-tools-redesign/specs/mcp-public-api/spec.md` | En §1.4 de history, especificar: default `horas=24`, default limit=50, max limit=200. |
| **B4** | Resolver contradicción C3 (stats fusionada) | `openspec/changes/mcp-tools-redesign/proposal.md` y spec | Decidir si history incluye conteos agregados o si stats sigue siendo Advanced. Actualizar ambos documentos. |

### Cambios recomendados (no bloqueantes pero fuertemente sugeridos)

| # | Acción | Archivo | Detalle |
|---|---|---|---|
| **R1** | Decidir no incluir Vision en PR4 | `src/apoch/public_api/coordinator.py` y spec | Simplificar PR4: history funciona solo con Chronicle. Vision se añade en un Minor futuro. Actualizar Internal Mapping y docstring. |
| **R2** | Documentar mapeo `tipo=tool` → `tool_invocation` | `src/apoch/public_api/coordinator.py` | Añadir comentario explícito en el código sobre el mapeo. |
| **R3** | Especificar `suggested_action = None` para history | Spec §1.4 | History no produce acciones sugeridas. Documentar que `suggested_action` puede ser None. |
| **R4** | Resolver ZG4 (stats en summary) | Spec y tasks | History PUEDE incluir conteos por tipo en summary como metadato opcional. Documentar límite: solo conteo, no análisis. |

### Resumen

| Estado | Decisión |
|---|---|
| **Contradicciones CRITICAL** | 3 (C1, C5, C9) — todas requieren cambio en spec o código |
| **Zonas grises CRITICAL** | 3 (ZG1, ZG2, ZG3) — todas requieren definición de constantes o cambio en spec |
| **Tensiones CRITICAL** | 2 (T1, T2) — nombres de módulo en narrativa, límites no definidos |
| **PR4 PUEDE COMENZAR** | ❌ **NO** |

**Veredicto: HALT.** Realizar los cambios B1–B4 y R1–R4 antes de iniciar PR4. Sin estos cambios, la implementación partiría de un diseño incompleto con contradicciones activas.

Una vez realizados los cambios, actualizar este boundary review (cambiar `status: draft` a `status: approved`) y emitir un nuevo veredicto.

---

*Fin del documento. Este review no autoriza ni inicia la implementación de PR4. Es exclusivamente un análisis de frontera.*
