---
title: "API Boundary Review — apoch_status"
status: draft
phase: review
created: 2026-07-16
reviewers:
  - gentle-orchestrator
change: mcp-tools-redesign
---

# API Boundary Review — `apoch_status`

> **Propósito de este documento:** Verificar que el diseño de `apoch_status` (PR2) es mínimo, enfocado y no invade el territorio de otras herramientas de la API pública. Esto es un análisis exclusivo. No inicia implementación.

---

## 1. Responsabilidad exacta

**Una sola frase:** Proveer una vista general unificada del estado actual del sistema en el momento de la consulta, combinando el estado de componentes activos, problemas detectados y actividad muy reciente, sin diagnosticar causas, sin recomendar acciones, sin mostrar historial completo, sin medir productividad y sin exponer implementación interna.

### Zona gris documentada

| Frontera | Dónde trazar la línea |
|---|---|
| `apoch_status` vs `apoch_health` | `status` **muestra** que hay un problema (hecho). `health` **diagnostica** el problema (interpretación, causa, severidad 🟢/🟡/🔴 como clasificación primaria). `status` puede usar 🟢/🟡/🔴 como resumen visual, pero nunca incluye "posible causa" ni "impacto". |
| `apoch_status` vs `apoch_history` | `status` incluye **actividad muy reciente** (últimos N eventos, scope deliberadamente acotado). `history` responde **cualquier rango temporal** con filtros y narrativa. La línea: status solo muestra "lo último que pasó" sin filtros ni navegación temporal. |
| `apoch_status` vs `apoch_recommend` | `status` puede incluir una **recomendación rápida** si Oracle responde, pero es un campo más, no el propósito. `recommend` existe exclusivamente para responder "qué hacer ahora". Status nunca prioriza ni estructura la respuesta alrededor de la recomendación. |
| `apoch_status` vs `apoch_progress` | `status` NO consulta Pulse. No mide productividad, tendencias ni evolución. Progreso es "cómo voy en el tiempo"; status es "qué pasa ahora". |
| `apoch_status` vs `apoch_insights` | `status` NO consulta Optimizer. No busca patrones ni oportunidades de mejora. Insights responde "qué patrones ves"; status responde "qué está pasando ahora". |
| `apoch_status` vs `apoch_logs` | `status` NO muestra entradas de log crudas. La actividad reciente se presenta como narrativa de alto nivel, no como líneas de log. Logs es para debugging técnico. |

---

## 2. Preguntas que responde

### 2.1 Catálogo completo de preguntas

| # | Pregunta | Responde | Clasificación |
|---|---|---|---|
| 1 | ¿Está funcionando el sistema? | ✅ Sí, mediante el estado general (🟢/🟡/🔴) | **Esencial** |
| 2 | ¿Qué componentes están activos en este momento? | ✅ Sí, lista de componentes activos y su estado | **Esencial** |
| 3 | ¿Hay algún problema ahora mismo? | ✅ Sí, problemas detectados por Guardian | **Esencial** |
| 4 | ¿Qué pasó recientemente en el sistema? | ✅ Sí, actividad muy reciente (Chronicle, scope acotado) | **Esencial** |
| 5 | ¿Hay algo que requiera mi atención? | ✅ Sí, a través de `suggested_action` / recomendación rápida de Oracle | **Opcional** |
| 6 | ¿Cuándo fue la última vez que hubo actividad? | ✅ Sí, inferible de la actividad reciente | **Opcional** |
| 7 | ¿Cuántos eventos ocurrieron? | ❌ No — eso es métrica cuantitativa, no estado | **Fuera del alcance** |
| 8 | ¿Por qué falló un componente? | ❌ No — eso es diagnóstico (pertenece a `health`) | **Fuera del alcance** |
| 9 | ¿Qué debería hacer ahora específicamente? | ❌ No — eso es recomendación priorizada (pertenece a `recommend`) | **Fuera del alcance** |
| 10 | ¿Cómo ha sido mi productividad? | ❌ No — eso es tendencia (pertenece a `progress`) | **Fuera del alcance** |
| 11 | ¿Qué patrones de uso detectas? | ❌ No — eso es análisis (pertenece a `insights`) | **Fuera del alcance** |
| 12 | Dame los logs del sistema | ❌ No — eso es debugging técnico (pertenece a `logs`) | **Fuera del alcance** |
| 13 | ¿Qué pasó ayer entre las 14:00 y 16:00? | ❌ No — eso es histórico filtrado (pertenece a `history`) | **Fuera del alcance** |

### 2.2 Regla de pertenencia

Si una pregunta requiere filtros, rangos de tiempo, interpretación estadística, diagnóstico causal, o acceso a datos que no son del momento actual — **no pertenece a `apoch_status`**.

---

## 3. Información que devuelve

### 3.1 Obligatoria (siempre presente)

| Campo | Origen | Descripción |
|---|---|---|
| `api_version` | Constante | Siempre `"1.0"` (ADR-005) |
| `summary` | Coordinator | Estado general en una línea. Ej: "🟢 Todos los sistemas operativos" / "🟡 Sistema funcionando con limitaciones" |
| `explanation` | Coordinator | Contexto breve. Ej: "3 componentes activos, sin errores, última actividad hace 2m" |
| `evidence` | Multi-módulo | Lista de `EvidenceSource` con los datos que respaldan la respuesta (nunca expone módulos internos por nombre en el texto, solo en el campo técnico `source`) |
| `confidence` | Coordinator | Nivel de confianza (`0.00`–`1.00`). Siempre HIGH en condiciones normales (es estado actual, no predicción). Baja cuando hay módulos que no responden. |
| `generated_at` | Coordinator | Timestamp ISO 8601 de generación |
| `data_freshness` | Coordinator | Antigüedad máxima de los datos fuente en segundos |

### 3.2 Obligatoria condicional (depende de disponibilidad de módulos)

| Información | Dependencia | Condición |
|---|---|---|
| Componentes activos | Vision (module_state) | Lista de componentes con su estado (LOADED, RUNNING, STOPPED, FAILED). Sin Vision no se puede reportar. |
| Problemas detectados | Guardian (all_diagnostics) | Lista de problemas activos con descripción de alto nivel. Sin Guardian no se puede reportar. |
| Actividad reciente | Chronicle (query) | Últimos eventos en narrativa de una línea. Sin Chronicle no se reporta. |

### 3.3 Opcional (valor añadido si el módulo responde)

| Información | Dependencia | Comportamiento si no disponible |
|---|---|---|
| Recomendación rápida | Oracle | No se incluye. El `suggested_action` puede ser "Ninguna acción requerida" o derivarse de otros módulos. |
| `suggested_action` enriquecido | Oracle + resto | Si Oracle no responde, `suggested_action` se reduce a "Ninguna acción requerida" o "Revise los problemas detectados". |

### 3.4 Nunca permitida

| Información | Motivo |
|---|---|
| PID, RSS, threads, Python version, platform | Expone implementación interna. Eso era `vision_system` (eliminado). |
| Nombres de clase, rutas de archivo, nombres de módulo Python | Viola P6 (nunca expone implementación). |
| IDs de eventos de Chronicle | Viola separación consulta/implementación. Eso era `chronicle_query`. |
| SQL, nombres de tabla, clave primaria | Expone almacenamiento interno. |
| Tracebacks, stack traces | Viola anti-patterns de spec §1.9. |
| Configuración de módulos | Eso era `vision_config` (ahora Internal). |
| Diagnóstico detallado con causas | Pertenece a `apoch_health`. |
| Narrativa histórica completa | Pertenece a `apoch_history`. |
| Recomendación priorizada | Pertenece a `apoch_recommend`. |
| Métricas de productividad | Pertenece a `apoch_progress`. |
| Patrones de uso | Pertenece a `apoch_insights`. |
| Entradas de log crudas | Pertenece a `apoch_logs`. |
| Costes por token, nombres de modelo | Métricas internas no públicas. |
| Orden de ejecución de módulos | Viola ADR-007. El orden es indeterminado. |

---

## 4. Módulos que consulta

### 4.1 Mapa de módulos

| Módulo | Clasificación | Datos que aporta | Justificación |
|---|---|---|---|
| **Vision** | **Obligatorio** | Estado de componentes (`module_state`), lista de módulos activos con su estado lifecycle | Sin Vision no es posible determinar qué componentes están funcionando. Es el pilar de "componentes activos". |
| **Guardian** | **Obligatorio** | Problemas detectados (`all_diagnostics`), módulos en estado FAILED con error resumido | Sin Guardian no es posible detectar problemas activos. Es el pilar de "problemas detectados". |
| **Chronicle** | **Obligatorio** | Actividad reciente (`query` con filtro mínimo), últimos eventos | Sin Chronicle no hay visibilidad de "qué pasó recientemente". Es el pilar de "actividad reciente". |
| **Oracle** | **Opcional** | Recomendación rápida (`oracle.status` o recomendaciones) | Aporta valor añadido pero no es parte del contrato mínimo de status. Sin Oracle, status sigue siendo completo. |
| **Pulse** | **Nunca** | Mediciones de productividad | Pulse responde a "¿cómo voy?" (progreso). No aporta al estado actual del sistema. Si se consultara Pulse, status empezaría a invadir el territorio de progress. |
| **Optimizer** | **Nunca** | Hipótesis, patrones, optimizaciones | Optimizer responde a "¿qué patrones ves?" (insights). No aporta al estado actual. Si se consultara Optimizer, status empezaría a invadir insights. |

### 4.2 Regla de acoplamiento

`apoch_status` solo conoce los módulos a través de `ServiceRegistry` (duck-typed). No importa ningún módulo directamente. Esto cumple ADR-001 y garantiza que la herramienta sobrevive a cambios de implementación interna.

### 4.3 Dependencias transitivas (prohibidas)

`apoch_status` NO debe consultar módulos a través de otros módulos. Ejemplo prohibido: pedirle a Vision que consulte a Guardian. Cada módulo se consulta directamente via `ServiceRegistry`.

---

## 5. Qué NO debe hacer

### 5.1 Restricciones funcionales

1. **No diagnostica causas.** Ante un problema, status muestra "Módulo X en estado FAILED". No dice "por qué falló", "desde cuándo", "impacto estimado". Eso es responsabilidad de `health`.
2. **No recomienda acciones priorizadas.** Status puede sugerir "Revise los problemas detectados" o incluir una nota de Oracle, pero no estructura su respuesta alrededor de "la siguiente acción de mayor impacto". Eso es `recommend`.
3. **No interpreta patrones.** Status no busca tendencias, correlaciones ni oportunidades de mejora. Eso es `insights`.
4. **No optimiza.** Status no sugiere cambios de configuración, cierre de procesos, ni ninguna acción que modifique el sistema.
5. **No ejecuta acciones.** Status es consulta pura. Nunca llama a métodos que muten estado.
6. **No muestra historial completo.** La actividad reciente en status está acotada (ej. últimos 5 eventos o últimos 5 minutos). No acepta filtros temporales.
7. **No expone implementación interna.** No muestra módulos consultados, orden de ejecución, nombres de clase, rutas, PID, memoria, threads.
8. **No deriva a otra herramienta.** La respuesta de status es COMPLETA. Puede mencionar "Más información en apoch_health" como nota, pero nunca como requisito para entender la respuesta (P5).
9. **No es un dump de `vision_state`.** La respuesta es una vista agregada e interpretada, no una proyección de datos internos.
10. **No acepta argumentos de entrada.** Status no tiene parámetros. Zero configuración. Zero filtros. Esto previene el feature creep.

### 5.2 Restricciones técnicas

11. **No tiene estado entre llamadas.** Cada invocación de status es independiente (non-goal #6 del spec).
12. **No depende del orden de ejecución de módulos.** El orden es indeterminado (ADR-007).
13. **No usa timeout global.** Los módulos tienen timeouts individuales. Los módulos lentos no afectan a los rápidos.
14. **No propaga excepciones de módulos.** Las excepciones se capturan y el módulo se marca como no disponible (ADR-007).

### 5.3 Restricciones de evolución

15. **No añade nuevos módulos sin spec change.** Cualquier nuevo módulo consultado por status requiere aprobación en spec.
16. **No crea nuevas secciones en la respuesta sin spec change.** La estructura está definida: estado general, componentes, problemas, actividad, acción sugerida. Nuevas secciones requieren revisión de frontera.
17. **No aumenta la latencia objetivo sin justificación.** Tiempo objetivo: < 2 segundos (spec §1.4). No se degrada sin revisión.

---

## 6. Matriz de fallos de módulos

### 6.1 Escenarios individuales

| Escenario | Módulos disponibles | Respuesta | Confidence | Código |
|---|---|---|---|---|
| **TODO OK** | V + G + C + O | 🟢 Summary con estado general, componentes activos, sin problemas, actividad reciente, sugerencia opcional | HIGH (≥0.90) | — |
| **Vision falla** | ~~V~~ + G + C + O | 🟡 "Sistema funcionando con limitaciones — no se pudo determinar estado de todos los componentes". Se usa Guardian `all_diagnostics` para inferir estados parciales. Sin lista de componentes activos. | MEDIUM (0.50–0.74) | — |
| **Guardian falla** | V + ~~G~~ + C + O | 🟡 "Sistema funcionando — no se pudieron verificar problemas". Se muestran componentes y actividad, pero no se confirma la ausencia de problemas. | MEDIUM (0.50–0.74) | — |
| **Chronicle falla** | V + G + ~~C~~ + O | 🟢 "Sistema funcionando — sin datos de actividad reciente". Se muestran componentes y problemas. Sin actividad. | HIGH (≥0.90) para estado, bajo para actividad | — |
| **Oracle falla** | V + G + C + ~~O~~ | 🟢 Idem TODO OK pero sin sugerencia de Oracle. `suggested_action` = "Ninguna acción requerida". | HIGH (≥0.90) | — |
| **Vision + Oracle fallan** | ~~V~~ + G + C + ~~O~~ | 🟡 Sin componentes, sin sugerencia. Solo problemas y actividad. | MEDIUM (0.50–0.74) | — |
| **Guardian + Oracle fallan** | V + ~~G~~ + C + ~~O~~ | 🟡 Sin problemas confirmados, sin sugerencia. Solo componentes y actividad. | MEDIUM (0.50–0.74) | — |
| **Chronicle + Oracle fallan** | V + G + ~~C~~ + ~~O~~ | 🟢 Sin actividad, sin sugerencia. Componentes y problemas disponibles. | MEDIUM (0.50–0.74) | — |

### 6.2 Escenarios de fallo múltiple severo

| Escenario | Módulos disponibles | Respuesta | Confidence | Código |
|---|---|---|---|---|
| **Vision + Guardian fallan** | ~~V~~ + ~~G~~ + C + O | 🟡 "Actividad reciente disponible pero no se pudo determinar estado de componentes ni problemas". Solo actividad (y sugerencia opcional). Respuesta muy parcial. | LOW (0.25–0.49) | — |
| **Vision + Chronicle fallan** | ~~V~~ + G + ~~C~~ + O | 🟡 "Problemas detectados — no se pudo determinar estado de componentes ni actividad reciente". Solo problemas. | LOW (0.25–0.49) | — |
| **Guardian + Chronicle fallan** | V + ~~G~~ + ~~C~~ + O | 🟡 "Componentes activos — no se pudieron verificar problemas ni actividad reciente". Solo estados de módulos. | LOW (0.25–0.49) | — |
| **Vision + Guardian + Chronicle fallan** | ~~V~~ + ~~G~~ + ~~C~~ + O | 🟡 "Solo disponible recomendación rápida — sin datos de estado del sistema". No se puede determinar estado general. | VERY_LOW (0.00–0.24) | `ERR_NO_DATA` (borderline) |
| **Solo Vision disponible** | V + ~~G~~ + ~~C~~ + ~~O~~ | 🟡 "Componentes activos — sin información de problemas ni actividad reciente". | LOW (0.25–0.49) | — |
| **Solo Guardian disponible** | ~~V~~ + G + ~~C~~ + ~~O~~ | 🟡 "Problemas detectados — sin información de componentes ni actividad reciente". | LOW (0.25–0.49) | — |
| **Solo Chronicle disponible** | ~~V~~ + ~~G~~ + C + ~~O~~ | 🟡 "Actividad reciente disponible — sin información de estado del sistema". | LOW (0.25–0.49) | — |
| **Solo Oracle disponible** | ~~V~~ + ~~G~~ + ~~C~~ + O | ⚠️ Respuesta no recomendable. Oracle solo no constituye "estado del sistema". | VERY_LOW (0.0–0.24) | `ERR_NO_DATA` |
| **NINGÚN módulo responde** | Ninguno | 🔴 No se puede generar respuesta. El sistema no tiene datos para informar estado. | 0.0 | `ERR_TIMEOUT` |

### 6.3 Notas sobre la matriz

- **Ningún escenario produce crash.** La herramienta siempre responde, incluso si es con un código de error. Esto es mandatorio por ADR-004.
- **La ausencia de Oracle nunca es error.** Oracle es opcional por diseño. Si no responde, simplemente no hay recomendación rápida.
- **La frontera entre respuesta degradada y error:** cuando hay 0 evidence sources (o solo Oracle), se debe retornar `ERR_NO_DATA` o `ERR_TIMEOUT`. El diseño actual en `_build_success_response` requiere al menos 1 source no-None.
- **Confidence refleja completitud:** más módulos disponibles = mayor confidence. El spec dice "confidence siempre HIGH" para el happy path, pero en degradación baja naturalmente.
- **Tensión en el spec:** El spec §1.4 dice "Confidence: siempre HIGH (es estado actual, no predicción)" pero ADR-004 muestra confidence MEDIUM en degradación. La interpretación correcta es: confidence es HIGH *en condiciones normales* (todos los módulos requeridos responden). En degradación, baja. Esto debe reflejarse en la implementación.

---

## 7. Future Creep Review

### 7.1 Riesgos de crecimiento incorrecto

| # | Riesgo | Síntoma | Herramienta invadida |
|---|---|---|---|
| 1 | Añadir diagnóstico de causas | Status empieza a decir "Módulo X falló por error de conexión en Y" | `health` |
| 2 | Añadir historial navegable | Status acepta `horas` o `desde` como parámetros | `history` |
| 3 | Añadir recomendaciones priorizadas | Status empieza a devolver "Next Action" como campo principal | `recommend` |
| 4 | Añadir métricas de productividad | Status incluye "work units completadas", "tasa de error" | `progress` |
| 5 | Añadir patrones de uso | Status incluye "se detectó que trabajas mejor por la mañana" | `insights` |
| 6 | Añadir logs técnicos | Status incluye entradas de log crudas con nivel/timestamp | `logs` |
| 7 | Añadir inputs/filtros | Status empieza a aceptar argumentos opcionales (pierde simplicidad) | Varias |
| 8 | Añadir campos técnicos | Status incluye uptime, PID, versión de Python | `vision_system` (eliminado) |
| 9 | Añadir "modo detallado" | Status tiene dos modos de respuesta (terso/detallado) | Varias |
| 10 | Añadir acción de "resolver" | Status permite "resolver este problema" desde la respuesta | Violación P4 (consulta/acción) |
| 11 | Añadir estado de módulos no-Apoch | Status monitoriza procesos externos, DB, colas | Expansión de dominio no prevista |
| 12 | Dependencia de módulos futuros | Status empieza a consultar módulos de config, ejecución, etc. | Acoplamiento excesivo |

### 7.2 Reglas para impedir el crecimiento incorrecto

#### Regla 1: Sin parámetros de entrada
`apoch_status` no tiene ni tendrá parámetros. Cero. Si una funcionalidad requiere filtros, rangos o selección, pertenece a otra herramienta.

#### Regla 2: Prohibición de new sections sin spec change
La respuesta de status tiene EXACTAMENTE estas secciones: estado general, componentes activos, problemas detectados, actividad reciente, acción sugerida. Cualquier sección nueva requiere un spec change aprobado con boundary review.

#### Regla 3: Prohibición de new module dependencies sin spec change
Los únicos módulos que status consulta son Vision, Guardian, Chronicle y Oracle. Cualquier módulo adicional (Pulse, Optimizer, o futuros) requiere especificación, ADR y boundary review.

#### Regla 4: Una pieza de información = una herramienta
Si un dato nuevo que se quiere añadir a status ya es responsabilidad de otra herramienta (health, history, recommend, progress, insights, logs), no se añade a status. Punto.

#### Regla 5: Status no crece en profundidad, crece en amplitud
Status es una vista general. Si un área necesita más profundidad, se crea una herramienta específica (como ya existe health, history, etc.). Status no compite con ellas.

#### Regla 6: El nombre "status" es el ancla
La pregunta "¿Un usuario entendería esto como 'estado del sistema'?" es el test de fuego. Si la respuesta es dudosa, no pertenece a status.

#### Regla 7: Latencia máxima como límite de crecimiento
Tiempo objetivo: < 2 segundos. Cualquier añadido que empuje la latencia por encima de 2s requiere optimización o exclusión. Esto limita naturalmente el crecimiento.

#### Regla 8: Revisión periódica de frontera
Cada 6 meses, o antes de un MAJOR release, se realiza un boundary review de `apoch_status` contra todas las herramientas existentes para detectar solapamiento involuntario.

---

## 8. Definition of Done para PR2

### 8.1 Requisitos funcionales

- [ ] **8.1.1** `ApochCoordinator.status()` implementado consultando Vision, Guardian, Chronicle y Oracle via `ServiceRegistry`.
- [ ] **8.1.2** La respuesta incluye **siempre**: `api_version`, `summary`, `explanation`, `evidence`, `confidence`, `generated_at`, `data_freshness`.
- [ ] **8.1.3** La respuesta incluye **estado general** del sistema (OK / WARN / ERROR o 🟢/🟡/🔴) en `summary`.
- [ ] **8.1.4** La respuesta incluye **componentes activos** extraídos de Vision (`module_state`) cuando Vision está disponible.
- [ ] **8.1.5** La respuesta incluye **problemas detectados** extraídos de Guardian (`all_diagnostics`) cuando Guardian está disponible.
- [ ] **8.1.6** La respuesta incluye **actividad reciente** extraída de Chronicle (`query` con filtro acotado a últimos N eventos o última hora) cuando Chronicle está disponible.
- [ ] **8.1.7** La respuesta incluye **acción sugerida** (`suggested_action`) que refleje el estado: "Ninguna acción requerida", "Revise los problemas detectados", o recomendación de Oracle si está disponible.
- [ ] **8.1.8** Si Oracle está disponible, la respuesta puede incluir una **recomendación rápida** como parte del `suggested_action` o como nota en `explanation`. Nunca como estructura separada.
- [ ] **8.1.9** La respuesta NUNCA incluye: PID, RSS, threads, Python version, platform, nombres de clase, IDs de evento, SQL, tracebacks, configuración de módulos, orden de ejecución.

### 8.2 Requisitos técnicos

- [ ] **8.2.1** Status usa `_query_modules()` con timeouts individuales: Vision (1.0s), Guardian (0.5s), Chronicle (0.5s), Oracle (2.0s).
- [ ] **8.2.2** Las consultas a módulos se ejecutan en paralelo con `asyncio.gather(return_exceptions=True)` (ADR-007).
- [ ] **8.2.3** Timeouts y excepciones de módulos se capturan: el módulo se marca como no disponible, la respuesta continúa (ADR-004).
- [ ] **8.2.4** Si 0 módulos responden (todos timeout/error) → se retorna `ERR_TIMEOUT`.
- [ ] **8.2.5** Confidence se calcula como promedio de módulos disponibles vs. consultados (siguiendo `_calculate_confidence` existente).
- [ ] **8.2.6** `api_version` se establece desde la constante en `version.py` (ADR-005).
- [ ] **8.2.7** `generated_at` usa ISO 8601 con UTC.
- [ ] **8.2.8** `data_freshness` refleja la antigüedad de los datos más antiguos entre los módulos que respondieron.
- [ ] **8.2.9** `evidence` contiene una entrada por cada módulo que respondió, con source, confidence, collected_ago, based_on.
- [ ] **8.2.10** No se importa ningún módulo concreto (VisionModule, GuardianModule, etc.) en coordinator.py. Solo se usa duck-typing via ServiceRegistry.

### 8.3 Requisitos de pruebas

- [ ] **8.3.1** Test: Happy path — todos los módulos responden → respuesta completa con HIGH confidence.
- [ ] **8.3.2** Test: Sin actividad registrada — Chronicle vacío → "Sistema iniciado, sin actividad registrada".
- [ ] **8.3.3** Test: Problema detectado — Guardian reporta módulo en FAILED → 🟡/🔴 en estado general, problema en evidence.
- [ ] **8.3.4** Test: Timeout en un módulo (Vision) → respuesta parcial con confidence degradada.
- [ ] **8.3.5** Test: Timeout en un módulo (Oracle) → respuesta completa sin sugerencia de Oracle.
- [ ] **8.3.6** Test: Todos los módulos timeout → `ERR_TIMEOUT`.
- [ ] **8.3.7** Test: Vision no disponible (None en ServiceRegistry) → status funciona sin componentes.
- [ ] **8.3.8** Test: Guardian no disponible → status funciona sin problemas detectados.
- [ ] **8.3.9** Test: Chronicle no disponible → status funciona sin actividad reciente.
- [ ] **8.3.10** Test: Oracle no disponible → status funciona sin recomendación rápida.
- [ ] **8.3.11** Test: La respuesta no contiene campos prohibidos (PID, memoria, etc.).
- [ ] **8.3.12** Test: El formato de respuesta coincide con ToolResponse esperado.
- [ ] **8.3.13** Test: `api_version = "1.0"` en la respuesta.

### 8.4 Requisitos de UX

- [ ] **8.4.1** Un usuario nuevo entiende qué hace `apoch_status` solo con el nombre y la descripción en ≤30 segundos (P8 — Rule of 30 Seconds).
- [ ] **8.4.2** La respuesta es autosuficiente — no requiere llamar a otra herramienta para entenderla (P5).
- [ ] **8.4.3** `summary` es una sola línea que responde la pregunta "¿qué está pasando?"
- [ ] **8.4.4** `explanation` proporciona contexto breve sin jerga técnica.
- [ ] **8.4.5** La respuesta usa lenguaje natural, no estructuras de datos internas.

### 8.5 Requisitos de arquitectura

- [ ] **8.5.1** `ApochCoordinator.status()` no tiene estado — cada llamada es independiente.
- [ ] **8.5.2** Status no depende del orden de ejecución de módulos (ADR-007).
- [ ] **8.5.3** Status sobrevive a la eliminación de cualquier módulo opcional (Oracle). También sobrevive a la eliminación de módulos obligatorios con degradación.
- [ ] **8.5.4** Si mañana se reemplazan Vision, Guardian, Chronicle u Oracle por implementaciones diferentes, `apoch_status` no cambia (P7 — Intent Stability Rule).
- [ ] **8.5.5** No se registran otras herramientas públicas nuevas en este PR (registro progresivo, P10).
- [ ] **8.5.6** Ninguna herramienta existente se ve afectada por este PR.
- [ ] **8.5.7** La herramienta respeta el presupuesto de PR2 en `tasks.md`: ≤400 LOC netas, ≤15 archivos modificados.

### 8.6 Acceptance Gate (de tasks.md §2.2)

- [ ] **8.6.1** `apoch_status` es visible en `tools/list`.
- [ ] **8.6.2** Ninguna tool futura (health, history, recommend, progress, insights, logs) es visible en `tools/list`.
- [ ] **8.6.3** Ninguna herramienta pública devuelve `ERR_NOT_IMPLEMENTED` (solo status implementado, las demás no están registradas).
- [ ] **8.6.4** Ruff: `ruff check src/apoch/` pasa sin errores nuevos.
- [ ] **8.6.5** Pytest: `pytest tests/public_api/test_status.py -v` pasa completo.
- [ ] **8.6.6** Tipado: `mypy src/apoch/` pasa sin errores nuevos.

---

## Apéndice A: Mapa de decisiones de diseño pertinentes

| Decisión | Referencia | Impacto en status |
|---|---|---|
| ServiceRegistry tipado | ADR-001 | Status recibe servicios con tipo conocido, sin riesgos de string keys |
| ToolResponse unificado | ADR-002 | Status devuelve el mismo formato que todas las tools |
| Evidence + Confidence | ADR-003 | Status muestra qué módulos respondieron y con qué confianza |
| Timeout por módulo | ADR-004 | Status nunca crashea por módulo lento; degrada gracefulmente |
| API versionado | ADR-005 | Status incluye `api_version` para detección de cambios |
| Backward compatibility | ADR-006 | `vision_state` será alias de `apoch_status` en PR9 |
| Concurrencia async | ADR-007 | Status consulta módulos en paralelo con timeouts individuales |
| Sin parámetros de entrada | Spec §1.4 | Status es cero-configuración por diseño |
| Public Visibility Rule | ADR-001 §Política | Status solo se registra cuando está completo (PR2) |

## Apéndice B: Tensiones detectadas en el diseño actual

| Tensión | Descripción | Recomendación |
|---|---|---|
| Confidence "siempre HIGH" vs degradación | Spec §1.4 dice "Confidence: siempre HIGH (es estado actual, no predicción)" pero ADR-004 muestra confidence MEDIUM en degradación | Resolver en spec: confidence HIGH solo cuando todos los módulos requeridos responden. Degradado = confianza menor. |
| Actividad reciente vs history | ¿Cuánta actividad incluye status sin invadir history? No hay límite definido en la spec | Definir límite explícito: ej. últimos 5 eventos o últimos 5 minutos (el que sea menor). Documentar en spec. |
| Oracle como opcional vs parte del contrato | El spec §1.4 dice status contiene "recomendación rápida" pero también dice que Oracle es opcional | Dejar explícito que la recomendación rápida es OPCIONAL y no forma parte del contrato mínimo. |
| EvidenceSource con nombres de módulo | EvidenceSource.source = "Vision" expone el nombre del módulo interno. Esto podría violar P6 (nunca expone implementación) | Decidir si `apoch_status` expone "Vision" como `source` o usa un nombre genérico. La spec actual lo permite solo en el campo técnico `evidence[]`. Mantener así. |
| Validación de inicialización | Status no acepta inputs, pero ¿debe validar que el sistema esté inicializado? | Sí: si `ServiceRegistry` no tiene servicios (sistema no iniciado), status debe retornar `ERR_NOT_INITIALIZED`. |
| Límite de query a Chronicle | ¿Cuántos eventos debe pedir status a Chronicle? Si pide 100, se acerca a history. Si pide 3, puede ser insuficiente. | Definir constante: `STATUS_RECENT_EVENTS_LIMIT = 5` y `STATUS_RECENT_MINUTES = 5`. El que tenga menos eventos gana. |

---

*Fin del documento. Este review no autoriza ni inicia la implementación de PR2. Es exclusivamente un análisis de frontera.*
