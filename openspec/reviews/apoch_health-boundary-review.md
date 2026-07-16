---
title: "API Boundary Review — apoch_health"
status: draft
phase: review
created: 2026-07-16
reviewers:
  - gentle-orchestrator
change: mcp-tools-redesign
---

# API Boundary Review — `apoch_health`

> **Propósito de este documento:** Verificar que el diseño de `apoch_health` (PR3) es mínimo, enfocado y no invade el territorio de otras herramientas de la API pública. Esto es un análisis exclusivo. No inicia implementación.

---

## 1. Responsabilidad exacta de apoch_health

**Una sola frase:** Diagnosticar problemas activos del sistema clasificándolos por severidad (🟢/🟡/🔴) con su impacto, posible causa y acción recomendada por problema, sin resumir el estado general del sistema, sin recomendar la siguiente acción priorizada, sin mostrar historial, sin medir productividad y sin exponer implementación interna.

### Límites de frontera

| Herramienta | Health NO es | Health SÍ es |
|---|---|---|
| `apoch_status` | Health no es "vista general del sistema" | Health es "diagnóstico de problemas específicos" |
| `apoch_history` | Health no es "línea de tiempo de actividad" | Health es "instantánea de problemas actuales" |
| `apoch_recommend` | Health no es "siguiente acción priorizada" | Health puede incluir "acción sugerida por problema" |
| `apoch_progress` | Health no es "evolución de productividad" | Health es "estado de salud actual, no tendencias" |
| `apoch_insights` | Health no es "patrones de mejora" | Health es "problemas existentes, no oportunidades latentes" |
| `apoch_logs` | Health no es "registro técnico de eventos" | Health es "diagnóstico interpretado, no raw data" |

---

## 2. Comparación con status

### 2.1 ¿Hay superposición?

**Sí, potencial parcial.** Ambas herramientas pueden reportar que existe un problema y ambas usan la clasificación 🟢/🟡/🔴. Sin embargo, la **intención** y **profundidad** son diferentes:

| Dimensión | `apoch_status` | `apoch_health` |
|---|---|---|
| Pregunta | "¿Qué está pasando?" | "¿Tengo algún problema?" |
| Propósito | Vista general unificada | Diagnóstico de problemas |
| 🟢/🟡/🔴 | Resumen visual del estado global | Clasificación primaria de severidad diagnóstica |
| Problemas | "Hay un problema" (hecho) | "Por qué ocurre, qué impacto tiene, cómo resolverlo" |
| Causa | No incluye | Incluye posible causa por problema |
| Impacto | No incluye | Incluye impacto por problema |
| Acción sugerida | Una sola a nivel sistema | Una por problema + una a nivel sistema |
| Alcance | Sistema completo (componentes + actividad + problemas) | Solo problemas activos |
| Módulos | Vision + Guardian + Chronicle + Oracle | Guardian + Vision |

### 2.2 ¿Puede un usuario confundir la salida de health con status?

**Riesgo moderado.** Un usuario que ve 🟢 en `apoch_status` y luego 🟢 en `apoch_health` podría pensar que son redundantes. La diferencia debe ser evidente en el contenido:

- `status` 🟢 → "Todos los sistemas operativos. 3 componentes activos, sin errores, actividad reciente disponible."
- `health` 🟢 → "Sin problemas detectados. Todos los módulos reportan operación normal."

La clave: `status` comunica amplitud (qué componentes, qué actividad). `health` comunica profundidad (diagnóstico, causas, impacto). Ninguna herramienta debe incluir el contenido de la otra.

### 2.3 ¿Dónde está la línea exacta?

**La línea se traza en TRES dimensiones:**

1. **Profundidad del problema:** `status` dice "módulo X en FAILED". `health` dice "módulo X en FAILED debido a Y. Impacto: Z. Para resolverlo: W.".
2. **Alcance:** `status` cubre componentes + actividad + problemas. `health` cubre EXCLUSIVAMENTE problemas.
3. **Acción sugerida:** `status` tiene UNA acción a nivel sistema ("Ninguna acción requerida"). `health` tiene acciones por problema además de la acción global.

**Regla de oro:** Si una pieza de información explica POR QUÉ ocurre un problema o detalla su IMPACTO, pertenece a `health`. Si solo informa QUE existe un problema como parte de una vista más amplia, pertenece a `status`.

---

## 3. Preguntas que responde

### 3.1 Catálogo completo

| # | Pregunta | Responde | Clasificación |
|---|---|---|---|
| 1 | ¿Hay algún problema en el sistema ahora mismo? | ✅ Sí, clasificado por severidad | **Esencial** |
| 2 | ¿Qué tan grave es el problema? | ✅ Sí, mediante 🟢/🟡/🔴 | **Esencial** |
| 3 | ¿Qué impacto tiene el problema? | ✅ Sí, descripción del impacto por problema | **Esencial** |
| 4 | ¿Cuál es la posible causa del problema? | ✅ Sí, posible causa por problema | **Esencial** |
| 5 | ¿Qué puedo hacer para resolverlo? | ✅ Sí, acción recomendada por problema | **Esencial** |
| 6 | ¿Hay advertencias no críticas? | ✅ Sí, clasificación 🟡 para warnings | **Esencial** |
| 7 | ¿Qué módulos están fallando? | ✅ Sí, identificados en el diagnóstico | **Esencial** |
| 8 | ¿El sistema está sano? | ✅ Sí, 🟢 si no hay problemas | **Esencial** |
| 9 | ¿Cuántos problemas hay? | ✅ Sí, inferible del listado | **Opcional** |
| 10 | ¿Desde cuándo existe el problema? | ❌ No — eso es histórico (pertenece a `history`) | **Fuera del alcance** |
| 11 | ¿Qué debería hacer AHORA como prioridad? | ❌ No — eso es priorización (pertenece a `recommend`) | **Fuera del alcance** |
| 12 | ¿Por qué es esta la acción más importante? | ❌ No — eso es priorización con justificación (pertenece a `recommend`) | **Fuera del alcance** |
| 13 | ¿Cómo ha evolucionado la salud del sistema? | ❌ No — eso es tendencia (pertenece a `progress` o `history`) | **Fuera del alcance** |
| 14 | ¿Qué patrones de fallo detectas? | ❌ No — eso es análisis de patrones (pertenece a `insights`) | **Fuera del alcance** |
| 15 | Dame los logs de error del módulo X | ❌ No — eso es debugging técnico (pertenece a `logs`) | **Fuera del alcance** |
| 16 | ¿Está funcionando el sistema en general? | ❌ No — eso es estado general (pertenece a `status`) | **Fuera del alcance** |
| 17 | ¿Qué componentes están activos? | ❌ No — eso es inventario de componentes (pertenece a `status`) | **Fuera del alcance** |
| 18 | ¿Qué pasó recientemente? | ❌ No — eso es actividad reciente (pertenece a `status`/`history`) | **Fuera del alcance** |

### 3.2 Regla de pertenencia

Si una pregunta requiere **comparación temporal**, **priorización entre múltiples acciones**, **análisis de tendencias**, **detección de patrones**, o **acceso a datos técnicos crudos** — **no pertenece a `apoch_health`**.

---

## 4. Información que devuelve

### 4.1 Obligatoria (siempre presente)

| Campo | Origen | Descripción |
|---|---|---|
| `api_version` | Constante | Siempre `"1.0"` (ADR-005) |
| `summary` | Coordinator | 🟢/🟡/🔴 + frase resumen. Ej: "🟢 Sin problemas detectados" / "🔴 2 problemas críticos detectados" |
| `explanation` | Coordinator | Contexto breve del diagnóstico. Ej: "Guardian reporta 1 módulo en estado failed y 1 advertencia de rendimiento" |
| `evidence` | Guardian + Vision | Lista de `EvidenceSource` con los datos que respaldan el diagnóstico |
| `confidence` | Coordinator | Nivel de confianza (`0.00`–`1.00`). HIGH con Guardian disponible; MEDIUM si datos parciales; LOW si Guardian no disponible |
| `generated_at` | Coordinator | Timestamp ISO 8601 de generación |
| `data_freshness` | Coordinator | Antigüedad máxima de los datos fuente en segundos |

### 4.2 Obligatoria condicional (cuando hay problemas detectados)

| Información | Condición | Descripción |
|---|---|---|
| Lista de problemas con severidad | Guardian reporta problemas | Cada problema incluye: severidad, impacto, explicación, posible causa, acción recomendada |
| Clasificación 🟢/🟡/🔴 por problema | Guardian reporta problemas | Cada problema individual tiene su propia clasificación |
| Acción recomendada por problema | Guardian reporta problemas | Micro-acción para resolver ESE problema específico |

### 4.3 Opcional (valor añadido si Vision responde)

| Información | Dependencia | Comportamiento si no disponible |
|---|---|---|
| Estado de módulos afectados | Vision (`module_state`) | Health funciona solo con Guardian. El diagnóstico se basa exclusivamente en datos de Guardian. |
| Contexto adicional de módulos | Vision (`module_state`) | Vision puede enriquecer el diagnóstico indicando el estado lifecycle del módulo afectado. Sin Vision, health sigue siendo completo. |

### 4.4 Nunca permitida

| Información | Motivo |
|---|---|
| IDs de evento, SQL, nombres de tabla | Viola separación consulta/implementación. |
| Tracebacks, stack traces, códigos de error internos | Viola anti-patterns de spec §1.9. |
| Nombres de clase, rutas de archivo, nombres de módulo Python | Viola P6 (nunca expone implementación). |
| PID, RSS, threads, Python version, platform | Expone implementación interna. |
| Configuración de módulos | Pertenece a Internal (`vision_config`). |
| Recomendación priorizada ("Next Action") | Pertenece a `apoch_recommend`. |
| Línea de tiempo de actividad | Pertenece a `apoch_history`. |
| Métricas de productividad | Pertenece a `apoch_progress`. |
| Patrones de uso o mejora | Pertenece a `apoch_insights`. |
| Entradas de log crudas | Pertenece a `apoch_logs`. |
| Estado general del sistema (componentes activos, activity reciente) | Pertenece a `apoch_status`. |
| Orden de ejecución de módulos | Viola ADR-007. El orden es indeterminado. |
| Costes por token, nombres de modelo | Métricas internas no públicas. |
| Confidence estadística cruda (p-values, sample sizes) | Viola P6. Solo se muestra confidence global interpretada. |

---

## 5. Módulos que consulta

### 5.1 Mapa de módulos

| Módulo | Clasificación | Datos que aporta | Justificación |
|---|---|---|---|
| **Guardian** | **Obligatorio** | Diagnósticos del sistema (`all_diagnostics`): problemas activos con severidad, módulos afectados, descripción del error | Sin Guardian no hay diagnósticos. Es la fuente primaria de health. El propósito mismo de health es traducir los diagnósticos de Guardian a lenguaje humano. |
| **Vision** | **Opcional** | Estado de módulos (`module_state`): estado lifecycle (LOADED, RUNNING, STOPPED, FAILED) de cada módulo | Aporta contexto adicional sobre el estado actual de los módulos afectados. No es requerido porque Guardian ya proporciona la información diagnóstica. Vision enriquece pero no define. |
| **Chronicle** | **Nunca** | Eventos históricos | Chronicle responde a "¿qué pasó?" (history/status). No aporta al diagnóstico de problemas actuales. Si health consultara Chronicle, empezaría a invadir history. |
| **Oracle** | **Nunca** | Recomendaciones, predicciones | Oracle responde a "¿qué debería hacer?" (recommend). No aporta al diagnóstico. Si health usara Oracle para generar acciones, invadiría recommend. |
| **Pulse** | **Nunca** | Mediciones de productividad | Pulse responde a "¿cómo voy?" (progress). No aporta al diagnóstico de problemas. |
| **Optimizer** | **Nunca** | Hipótesis, patrones, optimizaciones | Optimizer responde a "¿qué patrones ves?" (insights). No aporta al diagnóstico de problemas actuales. |

### 5.2 Justificación detallada de módulos "Nunca"

#### Chronicle
**Riesgo:** Si health empezara a consultar Chronicle, podría determinar "desde cuándo existe este problema" o "qué eventos llevaron a este fallo". Eso es análisis histórico, que pertenece a `history` o `status` (actividad reciente).

**Límite estricto:** Health trabaja con el presente. No necesita saber cuándo empezó un problema ni qué eventos lo precedieron.

#### Oracle
**Riesgo:** Oracle podría sugerir la acción más importante para resolver los problemas detectados. Si health usara Oracle para priorizar entre múltiples problemas, estaría haciendo el trabajo de `recommend`.

**Límite estricto:** Health puede sugerir una acción por problema ("Para resolver X, haz Y"), pero NO prioriza entre problemas. La priorización es responsabilidad de `recommend`.

#### Pulse
**Riesgo:** Si health midiera el impacto de los problemas en la productividad (ej. "este problema ha reducido tu eficiencia en un 15%"), estaría invadiendo `progress`.

**Límite estricto:** Health describe el impacto del problema en el sistema, no en la productividad del usuario.

#### Optimizer
**Riesgo:** Optimizer podría identificar patrones de fallo recurrentes (ej. "el módulo X falla cada vez que Y"). Eso es detección de patrones, que pertenece a `insights`.

**Límite estricto:** Health detecta problemas actuales. No busca patrones ni oportunidades de mejora a largo plazo.

### 5.3 Regla de acoplamiento

`apoch_health` solo conoce los módulos a través de `ServiceRegistry` (duck-typed). No importa ningún módulo directamente. Esto cumple ADR-001 y garantiza que la herramienta sobrevive a cambios de implementación interna.

### 5.4 Dependencias transitivas (prohibidas)

`apoch_health` NO debe consultar módulos a través de otros módulos. Ejemplo prohibido: pedirle a Guardian que consulte a Vision. Cada módulo se consulta directamente via `ServiceRegistry`.

---

## 6. Qué NO debe hacer

### 6.1 Restricciones funcionales

1. **No recomienda acciones priorizadas.** Health puede incluir "acción recomendada" por problema (micro-acción), pero no estructura su respuesta alrededor de "la siguiente acción de mayor impacto". Eso es `recommend`.

2. **No muestra historial de problemas.** Health no dice "este problema comenzó hace 3 horas" ni "ha ocurrido 5 veces antes". Eso es `history`.

3. **No interpreta productividad ni patrones.** Health no dice "este problema ha reducido tu productividad" ni "sigue un patrón de fallo los viernes". Eso es `progress`/`insights`.

4. **No muestra logs técnicos.** Health no incluye entradas de log, timestamps de error, ni mensajes de debug. Eso es `logs`.

5. **No resume el estado general del sistema.** Health no lista componentes activos, actividad reciente ni estado de módulos no afectados. Eso es `status`.

6. **No ejecuta acciones.** Health es consulta pura. Nunca llama a métodos que muten estado.

7. **No expone implementación interna.** No muestra módulos consultados, orden de ejecución, nombres de clase, rutas, códigos de error internos, ModuleDiagnostics crudo.

8. **No deriva a otra herramienta.** La respuesta de health es COMPLETA. Puede mencionar "Más información en apoch_recommend" como nota, pero nunca como requisito para entender la respuesta (P5).

9. **No acepta argumentos de entrada.** Health no tiene parámetros. Zero configuración. Zero filtros. Esto previene el feature creep.

10. **No muestra diagnósticos crudos de Guardian.** Los `ModuleDiagnostics` internos se traducen a lenguaje humano. No se exponen campos como `error_code`, `module_id`, `timestamp` internos.

### 6.2 Restricciones técnicas

11. **No tiene estado entre llamadas.** Cada invocación de health es independiente (non-goal #6 del spec).

12. **No depende del orden de ejecución de módulos.** El orden es indeterminado (ADR-007).

13. **No usa timeout global.** Los módulos tienen timeouts individuales. Guardian (0.5s), Vision (0.5s).

14. **No propaga excepciones de módulos.** Las excepciones se capturan y el módulo se marca como no disponible (ADR-007).

### 6.3 Restricciones de evolución

15. **No añade nuevos módulos sin spec change.** Cualquier nuevo módulo consultado por health requiere aprobación en spec y boundary review.

16. **No añade nuevas secciones en la respuesta sin spec change.** La estructura está definida: clasificación global + lista de problemas con severidad, impacto, causa, acción. Nuevas secciones requieren revisión de frontera.

17. **No aumenta la latencia objetivo sin justificación.** Tiempo objetivo: < 2 segundos (spec §3.4). No se degrada sin revisión.

---

## 7. Matriz de fallos

### 7.1 Escenarios individuales

| Escenario | Guardian | Vision | Respuesta | Confidence | Código |
|---|---|---|---|---|---|
| **Sin problemas** | ✅ (sin problemas) | ✅ | 🟢 "Sin problemas detectados" + evidencia de Guardian y Vision | HIGH (>=0.90) | — |
| **Sin problemas, Vision falla** | ✅ (sin problemas) | ❌ timeout | 🟢 "Sin problemas detectados" + evidencia solo de Guardian | HIGH (0.75–0.89) | — |
| **Advertencia activa** | ✅ (warnings) | ✅ | 🟡 "N advertencias detectadas" + detalle por warning: impacto, posible causa, acción | HIGH (>=0.90) | — |
| **Problema crítico** | ✅ (errors/critical) | ✅ | 🔴 "N problemas críticos detectados" + detalle por problema: severidad, impacto, causa, acción | HIGH (>=0.90) | — |
| **Problemas mixtos** | ✅ (warnings + critical) | ✅ | 🔴 Clasificación global según el problema más severo + lista completa | HIGH (>=0.90) | — |
| **Advertencia, Vision falla** | ✅ (warnings) | ❌ timeout | 🟡 Con diagnóstico de Guardian, sin contexto de Vision | MEDIUM (0.50–0.74) | — |
| **Crítico, Vision falla** | ✅ (errors) | ❌ timeout | 🔴 Con diagnóstico de Guardian, sin contexto de Vision | MEDIUM (0.50–0.74) | — |
| **Guardian falla (timeout)** | ❌ timeout | ✅ | No se puede diagnosticar. Error: módulo requerido no disponible. | LOW (0.0–0.24) | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Guardian no disponible (None)** | ❌ None | ✅ | No se puede diagnosticar. Error: módulo requerido no cargado. | LOW (0.0–0.24) | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Guardian falla, Vision falla** | ❌ timeout | ❌ timeout | Sin datos de ningún módulo. | 0.0 | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Guardian sin datos (vacío)** | ✅ (vacío) | ✅ | 🟢 "Sin problemas detectados" (vacío = sin problemas) | HIGH (>=0.90) | — |

### 7.2 Escenarios de degradación combinada

| Escenario | Guardian | Vision | Respuesta | Confidence | Código |
|---|---|---|---|---|---|
| **Crítico + Guardian responde lento pero a tiempo** | ✅ (lento) | ✅ | 🔴 Respuesta completa, pero `data_freshness` elevado | HIGH (>=0.90) | — |
| **Guardian responde con error inesperado** | ❌ (excepción) | ✅ | Error: módulo falló inesperadamente | LOW (0.0–0.24) | `ERR_DEPENDENCY_UNAVAILABLE` |
| **Guardian + Vision responden datos inconsistentes** | ✅ (mod X failed) | ✅ (mod X running) | 🔴 Se prioriza Guardian sobre Vision para diagnóstico. Se documenta la discrepancia internamente (no expuesta al usuario). | MEDIUM (0.50–0.74) | — |

### 7.3 Notas sobre la matriz

- **Guardian es REQUERIDO.** Sin Guardian, health no puede funcionar. No hay fallback posible porque el diagnóstico es la razón de ser de la herramienta.
- **Vision es OPCIONAL.** Sin Vision, health sigue siendo completa. Solo pierde contexto adicional sobre el estado de módulos afectados.
- **Datos vacíos de Guardian = sin problemas.** Guardian reportar una lista vacía de diagnósticos significa que no hay problemas detectados. Esto produce 🟢 con HIGH confidence.
- **La inconsistencia Guardian vs Vision** debe resolverse a favor de Guardian (es la fuente autoritativa de diagnósticos). Vision proporciona contexto, no diagnóstico.
- **Ningún escenario produce crash.** La herramienta siempre responde, incluso si es con un código de error.
- **Confidence refleja completitud:** más módulos disponibles = mayor confidence. HIGH solo cuando Guardian está disponible (con o sin Vision).

---

## 8. Future Creep Review

### 8.1 Riesgos de crecimiento incorrecto

| # | Riesgo | Síntoma | Herramienta invadida |
|---|---|---|---|
| 1 | Añadir recomendación priorizada | Health empieza a devolver "Next Action" o a priorizar entre problemas | `recommend` |
| 2 | Añadir historial de problemas | Health incluye "este problema ha ocurrido N veces" o "comenzó hace X tiempo" | `history` |
| 3 | Añadir tendencias de salud | Health muestra gráficos de salud en el tiempo o "tu salud ha empeorado un 15%" | `progress` / `history` |
| 4 | Añadir patrones de fallo | Health detecta "los módulos fallan más los lunes" o "hay un patrón de error recurrente" | `insights` |
| 5 | Añadir estado general | Health incluye "3 componentes activos" o "actividad reciente: 5 eventos" | `status` |
| 6 | Añadir logs de error | Health incluye mensajes de error crudos con timestamps | `logs` |
| 7 | Añadir inputs/filtros | Health empieza a aceptar "módulo=vision" o "severidad=critical" como parámetros | Varias |
| 8 | Añadir acción de "resolver" | Health permite "resolver este problema" desde la respuesta | Violación P4 (consulta/acción) |
| 9 | Añadir "auto-repair" | Health no solo diagnostica sino que ejecuta la reparación | Violación P4 + mutación de estado |
| 10 | Añadir diagnóstico predictivo | Health empieza a decir "existe un 70% de probabilidad de fallo en 1 hora" | `insights` / `oracle` |
| 11 | Añadir estado de salud por módulo individual como vista principal | La respuesta se organiza por módulo en vez de por problema | `status` (componentes) |
| 12 | Añadir dependencia de módulos futuros | Health consulta módulos de config, ejecución, bases de datos externas | Acoplamiento excesivo |

### 8.2 Reglas para impedir el crecimiento incorrecto

#### Regla 1: Sin parámetros de entrada
`apoch_health` no tiene ni tendrá parámetros. Cero. Si una funcionalidad requiere filtros, rangos o selección (ej. "problemas del módulo X", "problemas críticos solamente"), pertenece a otra herramienta.

#### Regla 2: Health diagnostica problemas EXISTENTES, no predice ni previene
Si un dato habla de lo que PODRÍA ocurrir (predictivo) o de lo que DEBERÍA hacerse (recomendación priorizada), no pertenece a health. Solo pertenece a health lo que describe un problema QUE YA EXISTE.

#### Regla 3: Sin historial ni tendencias
Health es una instantánea del momento actual. Cualquier referencia temporal (línea de tiempo, frecuencia, duración, evolución) está fuera del alcance.

#### Regla 4: Una acción por problema, no una priorización
Health puede incluir "acción recomendada" para CADA problema individual. Pero no compara ni ordena estas acciones. La priorización es responsabilidad de `recommend`.

#### Regla 5: Sin nuevos módulos sin spec change
Los únicos módulos que health consulta son Guardian (obligatorio) y Vision (opcional). Cualquier módulo adicional requiere especificación, ADR y boundary review.

#### Regla 6: El nombre "health" es el ancla
La pregunta "¿Un usuario entendería esto como un 'diagnóstico de salud del sistema'?" es el test de fuego. Si la respuesta es dudosa, no pertenece a health.

#### Regla 7: Latencia máxima como límite de crecimiento
Tiempo objetivo: < 2 segundos. Cualquier añadido que empuje la latencia por encima de 2s requiere optimización o exclusión.

#### Regla 8: Revisión periódica de frontera
Cada 6 meses, o antes de un MAJOR release, se realiza un boundary review de `apoch_health` contra todas las herramientas existentes para detectar solapamiento involuntario.

---

## 9. Definition of Done para PR3

### 9.1 Requisitos funcionales

- [ ] **9.1.1** `ApochCoordinator.health()` implementado consultando Guardian (obligatorio) y Vision (opcional) via `ServiceRegistry`.
- [ ] **9.1.2** La respuesta incluye **siempre**: `api_version`, `summary`, `explanation`, `evidence`, `confidence`, `generated_at`, `data_freshness`.
- [ ] **9.1.3** La respuesta incluye **clasificación global** 🟢/🟡/🔴 en `summary`: 🟢 sin problemas, 🟡 advertencias, 🔴 problemas críticos.
- [ ] **9.1.4** Cuando hay problemas detectados, cada problema incluye: severidad, impacto, explicación, posible causa y acción recomendada.
- [ ] **9.1.5** Si Guardian reporta una lista vacía (sin problemas) → 🟢 "Sin problemas detectados" con HIGH confidence.
- [ ] **9.1.6** Si Guardian reporta problemas mixtos (warnings + criticals) → la clasificación global refleja el más severo (🔴 si hay algún crítico, 🟡 si solo warnings).
- [ ] **9.1.7** Si Vision está disponible, se incluye contexto adicional sobre el estado de módulos afectados en el diagnóstico.
- [ ] **9.1.8** Si Vision NO está disponible, la respuesta se construye solo con Guardian.
- [ ] **9.1.9** La respuesta NUNCA incluye: tracebacks, IDs internos, códigos de error internos, nombres de clase, rutas, ModuleDiagnostics crudo, logs, historial, tendencias, recomendaciones priorizadas.
- [ ] **9.1.10** La `suggested_action` global refleja la acción más relevante (la del problema más severo, o "Ninguna acción requerida" si no hay problemas).
- [ ] **9.1.11** La acción recomendada por problema es una micro-acción específica para resolver ESE problema, no una recomendación priorizada a nivel sistema.

### 9.2 Requisitos técnicos

- [ ] **9.2.1** Health usa `_query_modules()` con timeouts individuales: Guardian (0.5s), Vision (0.5s).
- [ ] **9.2.2** Las consultas a módulos se ejecutan en paralelo con `asyncio.gather(return_exceptions=True)` (ADR-007).
- [ ] **9.2.3** Timeouts y excepciones de módulos se capturan: el módulo se marca como no disponible, la respuesta continúa (ADR-004).
- [ ] **9.2.4** Si Guardian no responde (timeout, excepción, o None en ServiceRegistry) → se retorna `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **9.2.5** Confidence se calcula como promedio de módulos disponibles vs. consultados. HIGH (>=0.75) si Guardian responde + Vision responde. MEDIUM (0.50–0.74) si solo Guardian responde. LOW (<0.50) si Guardian no responde (se retorna error).
- [ ] **9.2.6** `api_version` se establece desde la constante en `version.py` (ADR-005).
- [ ] **9.2.7** `generated_at` usa ISO 8601 con UTC.
- [ ] **9.2.8** `data_freshness` refleja la antigüedad de los datos más antiguos entre los módulos que respondieron.
- [ ] **9.2.9** `evidence` contiene una entrada por cada módulo que respondió, con source, confidence, collected_ago, based_on.
- [ ] **9.2.10** No se importa ningún módulo concreto (GuardianModule, VisionModule, etc.) en coordinator.py. Solo se usa duck-typing via ServiceRegistry.
- [ ] **9.2.11** Los detalles de cada problema se estructuran dentro del formato ToolResponse (en `evidence` enriquecido, o como texto estructurado en `explanation`). **Ver tensión T3 en Apéndice B.**

### 9.3 Requisitos de pruebas

- [ ] **9.3.1** Test: Happy path — sin problemas — Guardian responde sin diagnósticos → 🟢 "Sin problemas detectados" con HIGH confidence.
- [ ] **9.3.2** Test: Happy path — advertencia activa — Guardian reporta warning → 🟡 con detalle del warning.
- [ ] **9.3.3** Test: Happy path — problema crítico — Guardian reporta módulo FAILED → 🔴 con posible causa y acción recomendada.
- [ ] **9.3.4** Test: Happy path — problemas mixtos — Guardian reporta warnings + criticals → 🔴 global con lista completa.
- [ ] **9.3.5** Test: Guardian no disponible (timeout) → `ERR_DEPENDENCY_UNAVAILABLE` con LOW confidence.
- [ ] **9.3.6** Test: Guardian no disponible (None en ServiceRegistry) → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **9.3.7** Test: Vision timeout → health funciona con Guardian solamente, confidence degradada a MEDIUM.
- [ ] **9.3.8** Test: Vision no disponible (None) → health funciona con Guardian solamente.
- [ ] **9.3.9** Test: Guardian + Vision timeout → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **9.3.10** Test: Guardian responde con error inesperado (excepción) → `ERR_DEPENDENCY_UNAVAILABLE`.
- [ ] **9.3.11** Test: La respuesta no contiene campos prohibidos (IDs internos, tracebacks, logs, etc.).
- [ ] **9.3.12** Test: El formato de respuesta coincide con ToolResponse esperado.
- [ ] **9.3.13** Test: `api_version = "1.0"` en la respuesta.
- [ ] **9.3.14** Test: La acción recomendada por problema no incluye lenguaje de priorización ("la más importante", "debes hacer esto primero").
- [ ] **9.3.15** Test: Guardian reporta datos vacíos → 🟢 sin problemas, no error.

### 9.4 Requisitos de UX

- [ ] **9.4.1** Un usuario nuevo entiende qué hace `apoch_health` solo con el nombre y la descripción en <=30 segundos (P8 — Rule of 30 Seconds).
- [ ] **9.4.2** La respuesta es autosuficiente — no requiere llamar a otra herramienta para entenderla (P5).
- [ ] **9.4.3** `summary` es una sola línea que responde la pregunta "¿tengo algún problema?"
- [ ] **9.4.4** `explanation` proporciona contexto breve sin jerga técnica.
- [ ] **9.4.5** La respuesta usa lenguaje natural, no estructuras de datos internas.
- [ ] **9.4.6** La clasificación 🟢/🟡/🔴 es visualmente distinguible y consistente con el uso en `apoch_status`.
- [ ] **9.4.7** Los problemas se listan del más severo al menos severo.
- [ ] **9.4.8** La acción recomendada por problema usa lenguaje imperativo claro ("Reinicie el módulo", "Revise la configuración de X"), no lenguaje especulativo ("podría considerar...").

### 9.5 Requisitos de arquitectura

- [ ] **9.5.1** `ApochCoordinator.health()` no tiene estado — cada llamada es independiente.
- [ ] **9.5.2** Health no depende del orden de ejecución de módulos (ADR-007).
- [ ] **9.5.3** Health sobrevive a la eliminación de Vision (módulo opcional). No sobrevive a la eliminación de Guardian (es su propósito, ver Intent Stability Rule).
- [ ] **9.5.4** Si mañana se reemplazan Guardian o Vision por implementaciones diferentes, `apoch_health` no cambia (P7 — Intent Stability Rule).
- [ ] **9.5.5** No se registran otras herramientas públicas nuevas en este PR (registro progresivo, P10).
- [ ] **9.5.6** Ninguna herramienta existente se ve afectada por este PR.
- [ ] **9.5.7** La herramienta respeta el presupuesto de PR3 en `tasks.md`: <=400 LOC netas, <=15 archivos modificados.

### 9.6 Acceptance Gate (de tasks.md §3.2)

- [ ] **9.6.1** `apoch_health` es visible en `tools/list`.
- [ ] **9.6.2** Ninguna tool futura (history, recommend, progress, insights, logs) es visible en `tools/list`.
- [ ] **9.6.3** Ninguna herramienta pública devuelve `ERR_NOT_IMPLEMENTED` (solo status y health implementados, las demás no están registradas).
- [ ] **9.6.4** Ruff: `ruff check src/apoch/` pasa sin errores nuevos.
- [ ] **9.6.5** Pytest: `pytest tests/public_api/test_health.py -v` pasa completo.
- [ ] **9.6.6** Tipado: `mypy src/apoch/` pasa sin errores nuevos.

---

## 10. Zonas grises con la Specification

### 10.1 Resumen de tensiones detectadas

| # | Tensión | Severidad | Descripción | Resolución propuesta |
|---|---|---|---|---|
| T1 | 🟢/🟡/🔴 duplicado entre status y health | **WARNING** | Ambas herramientas usan la misma clasificación visual. Un usuario puede pensar que son redundantes. | **Aceptar como diseño intencional.** El boundary review de status ya documentó esta frontera. La implementación debe garantizar que status NUNCA incluya "posible causa" ni "impacto". Health siempre incluye diagnóstico completo. La diferenciación está en el contenido, no en los emojis. |
| T2 | "Acción recomendada" por problema vs apoch_recommend | **WARNING** | El spec §3.4 dice que health incluye "acción recomendada" por problema. Esto puede confundirse con la responsabilidad de `recommend`. | **Límite explícito:** La acción de health es una micro-acción para resolver ESE problema específico ("Reinicie el módulo X"). `recommend` devuelve la acción de MAYOR IMPACTO a nivel sistema ("La siguiente acción es cerrar pestañas no utilizadas"). Health NO prioriza entre acciones. Recommend SÍ prioriza. |
| T3 | Estructura de per-problem details sin modelo específico | **INFO** | El spec requiere que cada problema incluya: impacto, explicación, posible causa, acción recomendada. Pero ToolResponse no tiene estructura para esto. EvidenceSource tampoco. | **Opción recomendada:** Extender ToolResponse con un campo `problems` o crear un `HealthResponse(ToolResponse)` con `problems: list[HealthProblem]`. Se recomienda crear el modelo para consistencia y testabilidad. Requiere ADR menor. |
| T4 | Superposición potencial Vision vs Guardian | **INFO** | Vision reporta `module_state` (LOADED/RUNNING/STOPPED/FAILED). Guardian reporta `all_diagnostics` con severidad. Ambos pueden reportar sobre el mismo módulo con información contradictoria. | **Regla:** Guardian es la fuente autoritativa para diagnósticos. Vision es contexto adicional. Si hay conflicto, prevalece Guardian. La discrepancia se registra internamente (metrics), no se expone al usuario. |
| T5 | Suggested action global vs per-problem | **INFO** | El ToolResponse tiene un solo `suggested_action`. Si hay múltiples problemas, cada uno con su acción, ¿cuál va en el campo global? | **Regla:** El `suggested_action` global refleja la acción del problema MÁS SEVERO. Si no hay problemas, "Ninguna acción requerida". Si hay múltiples problemas con la misma severidad, el primero en la lista. |
| T6 | Confidence "HIGH si Guardian disponible" vs degradación | **NINGUNA** | Spec §3.4 dice "Confidence: HIGH si hay datos de Guardian; MEDIUM si parcial; LOW si no disponible". Consistente con la matriz de fallos. Sin contradicción. | Sin acción requerida. |
| T7 | Acceptance Matrix del spec completamente marcada sin verificación real | **INFO** | El spec §1.8 tiene todos los checkboxes marcados como [x] para health, pero la herramienta aún no está implementada ni validada con usuarios. | Verificar cada criterio durante PR3. No asumir que están validados. |
| T8 | Problemas que solo Vision detecta pero Guardian no | **WARNING** | Vision detecta módulo FAILED pero Guardian no lo tiene en diagnostics. Health no lo reportaría, creando un falso negativo. | **Resolución:** Health debe priorizar Guardian como fuente de diagnósticos. Si Guardian no reporta el problema, health no lo reporta. El problema será visible en status (via Vision) hasta que Guardian lo confirme. Esto es correcto por diseño. |

### 10.2 Veredicto general

**No hay zonas grises CRITICAL que bloqueen PR3.**

Las tensiones T1, T2 y T8 son **WARNING** — requieren atención en la implementación pero están resueltas a nivel de diseño. T3 requiere una decisión de diseño menor (extender ToolResponse o crear HealthResponse). T4, T5 y T7 son **INFO** — requieren reglas claras en la implementación.

**PR3 PUEDE COMENZAR** siempre que:

1. Se resuelva T3 antes o durante la implementación (definir cómo se estructuran los problemas en la respuesta).
2. T1, T2 y T8 se documenten explícitamente en el código (comentarios en `coordinator.py` y docstring de `health()`).
3. Se verifique que la implementación respeta todas las restricciones de "Nunca permitida" en §4.4 y "Qué NO debe hacer" en §6.

---

## Apéndice A: Mapa de decisiones de diseño pertinentes

| Decisión | Referencia | Impacto en health |
|---|---|---|
| ServiceRegistry tipado | ADR-001 | Health recibe servicios con tipo conocido, sin riesgos de string keys |
| ToolResponse unificado | ADR-002 | Health devuelve el mismo formato que todas las tools (sin HealthResponse específico aún — ver T3) |
| Evidence + Confidence | ADR-003 | Health muestra qué módulos respondieron y con qué confianza |
| Timeout por módulo | ADR-004 | Health nunca crashea por módulo lento; degrada gracefulmente |
| API versionado | ADR-005 | Health incluye `api_version` para detección de cambios |
| Backward compatibility | ADR-006 | `guardian_diagnostics` y `guardian_all_diagnostics` serán alias de `apoch_health` en PR9 |
| Concurrencia async | ADR-007 | Health consulta módulos en paralelo con timeouts individuales |
| Sin parámetros de entrada | Spec §3.4 | Health es cero-configuración por diseño |
| Public Visibility Rule | ADR-001 §Política | Health solo se registra cuando está completo (PR3) |
| Intent Stability Rule | P7 | Health sobrevive a cambios de implementación de Guardian y Vision |
| Guardian como REQUERIDO | ADR-001 health docstring | Health depende de Guardian para su propósito. Sin Guardian, no hay diagnóstico. |
| Vision como OPCIONAL | ADR-001 health docstring | Vision enriquece pero no define. Health funciona sin Vision. |
| 🟢/🟡/🔴 en ambas tools | Spec §1.4 + §3.4 | Tanto status como health usan la misma clasificación visual con diferente profundidad (T1) |
| Acción recomendada | Spec §3.4 | Health incluye acción por problema, NO recomendación priorizada (T2) |

## Apéndice B: Tensiones detectadas en el diseño actual

| # | Tensión | Descripción | Recomendación |
|---|---|---|---|
| T1 | 🟢/🟡/🔴 duplicado entre status y health | Ambas herramientas usan la misma clasificación visual. Ya documentado en status boundary review. | Aceptar como diseño intencional. Garantizar que health SIEMPRE incluye diagnóstico completo (causa + impacto + acción) que status nunca incluye. |
| T2 | "Acción recomendada" vs recommend | Health incluye acción por problema; recommend da la acción priorizada a nivel sistema. La línea puede desdibujarse. | Documentar explícitamente: la acción de health resuelve UN problema específico. Recommend prioriza entre TODAS las acciones posibles. |
| T3 | Falta modelo para per-problem details | ToolResponse no tiene estructura nativa para lista de problemas con impacto, causa, acción. | Crear `HealthProblem` dataclass y `HealthResponse(ToolResponse)` con `problems: list[HealthProblem]`, o usar texto estructurado en `explanation`. Se recomienda crear el modelo. |
| T4 | Guardian vs Vision conflicto potencial | Ambos módulos pueden reportar datos inconsistentes sobre el mismo módulo. | Guardian es autoritativo para diagnóstico. Vision es solo contexto. La discrepancia se registra internamente. |
| T5 | suggested_action global ante múltiples problemas | Un solo campo `suggested_action` con múltiples problemas que tienen diferentes acciones. | Usar la acción del problema más severo como global. Documentar en código. |
| T6 | Inconsistencia en confidence del spec | Spec §3.4 dice "Confidence: HIGH si hay datos de Guardian; MEDIUM si parcial; LOW si no disponible". Pero "parcial" no está definido. | Definir: "parcial" = Guardian responde pero Vision no. "HIGH" = Guardian + Vision responden. "LOW" = Guardian no responde → error. |
| T7 | Acceptance Matrix pre-marcada | Todos los criterios del spec aparecen como cumplidos sin implementación. | Verificar cada criterio durante PR3. No asumir que están validados. |
| T8 | Problemas que solo Vision detecta | Vision detecta módulo FAILED pero Guardian no lo tiene en diagnostics. Health no lo reporta. | Aceptar como correcto: Guardian es la fuente autoritativa de diagnósticos. El módulo FAILED será visible en status (via Vision) hasta que Guardian lo registre. |

---

*Fin del documento. Este review no autoriza ni inicia la implementación de PR3. Es exclusivamente un análisis de frontera.*
