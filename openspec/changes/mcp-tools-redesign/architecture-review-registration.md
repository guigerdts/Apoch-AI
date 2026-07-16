# Architecture Review: Estrategia de Registro de Tools MCP

## Resumen Ejecutivo

**Estrategia recomendada: B — Registro Progresivo.**

La estrategia actual (A — registrar las 7 tools desde PR1B como stubs) pertenece al modelo de plataforma/tooling (Kubernetes, OpenTelemetry) donde el público objetivo son desarrolladores que necesitan visibilidad temprana. Apoch-AI es un producto que agentes LLM consumen vía MCP. Mostrar tools no funcionales a un modelo desperdicia contexto y ciclos de tool call, y contradice el principio de vertical slices del SDD.

Se recomienda modificar PR1B para NO registrar ninguna tool pública. Cada PR (PR2–PR8) registra exactamente la tool que implementa. Esto mantiene PRs atómicos, facilita rollback/git bisect, y no expone funcionalidad incompleta a los agentes.

---

## Comparación Detallada

### Estrategia A — Registro completo desde PR1B (actual)

PR1B registra las 7 tools como stubs. Cada PR posterior reemplaza un stub por una implementación real.

```
PR1B: register → [status*, health*, history*, recommend*, progress*, insights*, logs*]
PR2:  replace → [status,  health*, history*, recommend*, progress*, insights*, logs*]
PR3:  replace → [status,  health,  history*, recommend*, progress*, insights*, logs*]
...
* = stub ERR_NOT_IMPLEMENTED
```

### Estrategia B — Registro progresivo (recomendada)

PR1B NO registra ninguna tool. Cada PR registra exactamente una.

```
PR1B: infraestructura (sin tools registradas)
PR2:  register + implement → [status]
PR3:  register + implement → [status, health]
PR4:  register + implement → [status, health, history]
...
```

---

## Matriz de Trade-offs

| Criterio | Estrategia A | Estrategia B | Veredicto |
|----------|-------------|-------------|-----------|
| **Tamaño de PR** | PRs más pequeños (solo lógica) | PRs ligeramente más grandes (registro + lógica) | Empate |
| **Rollback** | Rollback de PR2 no elimina el tool del registro MCP | Rollback de PR2 elimina tool y registro atómicamente | ✅ **B** |
| **Git bisect** | Un cambio de stub a real puede no ser detectable como "tool funcional" | El commit que hace funcional una tool es exactamente donde aparece | ✅ **B** |
| **Superficie pública innecesaria** | 6 tools no funcionales visibles por MCP | Solo tools funcionales visibles | ✅ **B** |
| **Comunicación de estado real** | "Tenemos 7 tools" cuando solo 1 funciona | "Tenemos 1 tool" y es real | ✅ **B** |
| **Experiencia del modelo LLM** | El modelo prueba stubs, pierde contexto, recibe errores | El modelo solo ve tools que funcionan | ✅ **B** |
| **Esfuerzo por PR** | Menos líneas por PR de tool | Misma línea de registro adicional | Empate |
| **Testing** | Stub requiere test de "devuelve error" + después test de funcionalidad real | Un solo test de funcionalidad real | ✅ **B** |
| **Facilidad de implementación** | Ya está hecho (PR1B completo) | Requiere modificar PR1B | ✅ **A** (pero costo único) |

**Veredicto: 7-1-1 a favor de Estrategia B.**

---

## Análisis por Proyecto de Referencia

| Proyecto | Patrón | ¿Aplica a Apoch-AI? |
|----------|--------|---------------------|
| **Docker Engine** | Register-when-ready | **Sí.** Docker no registra endpoints no implementados. Un endpoint en el spec que devuelve 400 rompe clientes. Análogo: un tool MCP que devuelve ERR_NOT_IMPLEMENTED rompe la expectativa del modelo. |
| **Git CLI** | Register-when-ready | **Sí.** Git no tiene stubs para comandos planeados. Si un comando aparece en `--help`, debe funcionar. Análogo: la lista de tools que MCP expone debe ser el inventario de lo que funciona. |
| **FastAPI/Starlette** | Register-when-ready | **Sí.** No existe un mecanismo de stub en el framework. Si el desarrollador quiere un stub, debe escribirlo explícitamente como un handler 501. |
| **Kubernetes** | Feature gates (alpha/beta/GA) | **Parcial.** Kubernetes registra endpoints alpha PERO los oculta tras feature flags que requieren activación explícita. Apoch-AI no tiene feature gates en MCP. Sin ese mecanismo, el stub es público sin restricción. |
| **OpenTelemetry** | Alpha packages separados | **Parcial.** OTel expone señales en desarrollo como paquetes separados (`-alpha`). El usuario debe importarlos explícitamente. Análogo: si MCP soportara "tools experimentales ocultas por defecto", tendría sentido. No es el caso. |

**Conclusión de referencias:** Los 3 proyectos orientados a usuarios finales (Docker, Git, FastAPI) registran solo cuando la funcionalidad está completa. Los 2 proyectos que registran antes (Kubernetes, OTel) tienen mecanismos de gating que Apoch-AI no tiene. **El patrón correcto para Apoch-AI es Register-when-ready.**

---

## Respuestas Específicas

### 1. ¿Cuál estrategia sigue mejor la filosofía SDD?

**Estrategia B.** SDD se basa en vertical slices completos y entregables. Una tool que devuelve ERR_NOT_IMPLEMENTED no es un slice completo — es deuda técnica que no aporta valor hasta su PR correspondiente. Un slice SDD es: spec → design → implementación → tests → tool funcional. Registrar la tool antes viola ese ciclo porque la tool está "visible" pero no "funcional".

### 2. ¿Cuál produce PRs más pequeños?

Empate técnico. La diferencia es una línea de registro por PR (< 5 líneas). El costo de registro es despreciable comparado con la lógica de negocio de cada tool. No es un factor diferenciador.

### 3. ¿Cuál facilita rollback?

**Estrategia B.** Con B, revertir PR2 elimina la tool por completo del sistema. Con A, revertir PR2 deja el stub registrado — el tool sigue visible pero roto. Para limpiarlo hay que hacer un PR adicional.

### 4. ¿Cuál facilita git bisect?

**Estrategia B.** El commit donde una tool aparece por primera vez en el registro MCP es exactamente el commit donde se implementó. Con A, el commit de registro (PR1B) está desconectado del commit de implementación (PR2+). Un git bisect que encuentre PR1B no sabe si la tool es funcional o no.

### 5. ¿Cuál reduce superficie pública innecesaria?

**Estrategia B.** MCP expone lo que el modelo puede llamar. Cada tool no funcional es una llamada fallida que el modelo podría haber usado en otra cosa. En términos prácticos: cada vez que un modelo prueba `apoch_recommend` durante PR2-PR4, pierde un ciclo de tool call y contamina su contexto con un error.

### 6. ¿Cuál comunica mejor el estado real del proyecto?

**Estrategia B.** La lista de tools MCP es el inventario de capacidades del sistema. Si el inventario dice "tenemos 7 tools" pero 6 no funcionan, miente. Con B, la lista crece orgánicamente y cada entrada es una capacidad real.

### 7. ¿Qué hacen los proyectos maduros?

Ver tabla de referencias arriba. Docker, Git y FastAPI registran solo funcionalidad completa. Kubernetes y OTel registran antes pero con gating explícito. **Apoch-AI no tiene gating**, por lo tanto debe seguir el patrón Docker/Git.

### 8. ¿Existe alguna razón técnica para registrar desde PR1B?

**No.** No hay ninguna restricción técnica en FastMCP ni en OpenCode que exija registrar todas las tools de una vez. `register_module_tools()` puede llamarse múltiples veces, en diferentes fases, con diferentes tools. La infraestructura (ServiceRegistry, Coordinator, Manager wiring) ya está completa sin tools registradas.

El único argumento a favor sería "consistencia en la lista de tools desde el día 1", pero ese es un argumento cosmético, no técnico.

### 9. ¿Modificar ahora esta decisión tendría impacto negativo?

**Impacto bajo y localizado.** Los documentos SDD afectados:

| Documento | Cambio necesario | Impacto |
|-----------|-----------------|---------|
| **design.md** | ADR-001: la sección de registro muestra 7 tools desde PR1B. Cambiar a "cada PR registra su tool". | Bajo: un párrafo. |
| **tasks.md** | PR1B: eliminar "registrar coordinator tools". PR2-PR8: agregar "registrar tool X" a cada tarea. | Bajo: una línea por PR. |
| **coordinator.py** (PR1B) | Eliminar las 7 tool defs del registro. Mantener los stubs como métodos internos. | Medio: modificar archivo existente. |
| **manager.py** (PR1B) | No registrar coordinator tools en PR1B. Cada PR posterior agrega su registro. | Bajo. |
| **spec.md** | Sin cambios. La spec define el qué, no el orden de registro. | Ninguno. |
| **ADR-006 (Backward compat)** | Sin cambios. Los alias legacy se registran en PR9 independientemente. | Ninguno. |

**No hay impacto en:** Proposal, ADR-002 a ADR-005, ADR-007, Non-Goals, modelo de datos, contratos, testing strategy, migración.

---

## Riesgos de la Estrategia B

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| PR2 olvida registrar la tool | Baja | Incluir registro en la task y en los tests de validación |
| Inconsistencia temporal: PR1B existe pero ninguna tool responde | Ninguna | Es el estado actual antes de PR2 — no hay tools, es esperado |
| OpenCode no detecta tools hasta PR2 | Media | Es correcto: el sistema no tiene tools nuevas hasta que se implementan |
| Más líneas de boilerplate por PR | Baja | 1-3 líneas de registro por PR, costo insignificante |

---

## Recomendación Final

**Estrategia B — Registro Progresivo.**

**Acción inmediata:** Modificar PR1B para eliminar el registro de las 7 tools coordinator. Mantener los stubs como métodos internos del Coordinator (se usarán cuando cada PR registre su tool).

**Acción por PR:**

| PR | Acción |
|----|--------|
| PR1B (modificado) | Infraestructura completa. CERO tools registradas. |
| PR2 | `register_module_tools` para `apoch_status` + implementación |
| PR3 | `register_module_tools` para `apoch_health` + implementación |
| PR4 | `register_module_tools` para `apoch_history` + implementación |
| PR5 | `register_module_tools` para `apoch_recommend` + implementación |
| PR6 | `register_module_tools` para `apoch_progress` + implementación |
| PR7 | `register_module_tools` para `apoch_insights` + implementación |
| PR8 | `register_module_tools` para `apoch_logs` + implementación |

**Documentos a actualizar antes de continuar:**
1. `design.md` — ADR-001: cambiar diagrama de registro para reflejar registro progresivo
2. `tasks.md` — PR1B: eliminar registro de tools. PR2-PR8: agregar registro explícito
3. `coordinator.py` — eliminar registro de tools del `__init__` o del método que las expone
4. `manager.py` — eliminar registro de coordinator tools en PR1B

**Justificación técnica final:** No hay razón técnica para registrar stubs. Hay razones técnicas para no hacerlo: el modelo LLM probará tools no funcionales, desperdiciando contexto y tool calls. El principio de mínima sorpresa y el patrón de proyectos maduros (Docker, Git) favorecen registrar solo lo que funciona.
