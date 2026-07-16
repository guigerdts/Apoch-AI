# Design: Rediseño de la API Pública MCP de Apoch-AI

## Technical Approach

Nueva capa de coordinación (`apoch/public_api/`) que reemplaza el registro directo de herramientas de módulo (`get_tool_defs()`) por 7 herramientas públicas organizadas por intención humana. Cada herramienta orquesta los módulos internos vía duck-typed services y devuelve un contrato de respuesta unificado. La capa de compatibilidad hacia atrás redirige herramientas legacy (ej. `vision_state` → `apoch_status`) mediante alias en la registración de FastMCP.

## ADR-001: Orquestación y Coordinación

**Decisión**: Clase `ApochCoordinator` en `apoch/public_api/coordinator.py`. Recibe un `ServiceRegistry` tipado con servicios nombrados (inyectados por `AgentAdapterManager`). Cada herramienta pública es un método del coordinador que orquesta los módulos relevantes y agrega respuestas.

```python
# apoch/public_api/registry.py

@dataclass
class ServiceRegistry:
    vision: VisionModule | None = None
    chronicle: ChronicleModule | None = None
    guardian: GuardianModule | None = None
    pulse: PulseModule | None = None
    optimizer: OptimizerModule | None = None
    oracle: OracleModule | None = None
```

Ventajas frente a `dict[str, Any]`:
- **Autocomplete**: cada servicio tiene tipo conocido
- **Validación estática**: mypy/pyright detecta nombres incorrectos en compilación
- **Sin errores de string key**: no hay riesgo de `services["visoin"]`
- **Documentación viva**: los tipos documentan los servicios disponibles

El coordinator declara `ServiceRegistry` como dependencia única. `AgentAdapterManager` lo construye al iniciar y lo pasa al coordinator.

**Alternativas**:
| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| **Dispatcher genérico** (router + tasks) | Más flexible para 20+ tools, pero añade indirección innecesaria ahora | ❌ — premature abstraction |
| **Coordinator por dominio** (status, history, etc.) | Mayor separación, pero complejidad de 7 clases vs 1 | ❌ — 7 métodos en 1 clase es suficiente |
| **Módulo ApochModule** (lifecycle completo) | No hay estado entre llamadas; lifecycle añade overhead | ❌ — clase simple sin estado |

**Racional**: El coordinator es una capa de presentación que traduce intenciones humanas a consultas de módulos. No tiene estado, no tiene lifecycle. Recibe servicios por inyección. Cada herramienta es un método que:
1. Recolecta datos de módulos vía servicios
2. Aplica timeouts por módulo
3. Calcula confidence según disponibilidad
4. Ensambla respuesta unificada

**Política de Registro Progresivo** (Public Registration Policy):

1. El Coordinator puede contener métodos preparados para herramientas futuras.
2. Un método interno NO implica una herramienta pública registrada.
3. El registro MCP ocurre únicamente cuando la implementación está completa y validada.
4. El registro forma parte del PR funcional correspondiente (PR2–PR8).
5. Una herramienta incompleta nunca debe ser descubrible por un cliente MCP.
6. `tools/list` solo muestra herramientas totalmente implementadas.
7. Las tools legacy NO se ven afectadas: siguen registradas hasta PR9.

**Justificación:** Ver Architecture Review (`architecture-review-registration.md`). Proyectos maduros orientados a usuarios finales (Docker, Git, FastAPI) registran solo funcionalidad completa. Proyectos que registran antes (Kubernetes, OTel) requieren mecanismos de gating que Apoch-AI no posee en MCP.

**Flujo de inicialización (PR1B, sin tools registradas):**

```
AgentAdapterManager.start()
  │
  ├── 1. adapter.start()
  ├── 2. engine.start()  ← módulos se inician
  ├── 3. registry = ServiceRegistry(
  │       vision=engine.get_module("vision"),
  │       chronicle=engine.get_module("chronicle"),
  │       guardian=engine.get_module("guardian"),
  │       pulse=engine.get_module("pulse"),
  │       optimizer=engine.get_module("optimizer"),
  │       oracle=engine.get_module("oracle"),
  │     )
  └── 4. coordinator = ApochCoordinator(registry)
       └── (sin tools registradas — cada PR posterior registra la suya)
```

**Flujo de registro por PR:**

```
PR2:  adapter.register_module_tools("status", coordinator, ["apoch_status"])
PR3:  adapter.register_module_tools("health", coordinator, ["apoch_health"])
PR4:  adapter.register_module_tools("history", coordinator, ["apoch_history"])
PR5:  adapter.register_module_tools("recommend", coordinator, ["apoch_recommend"])
PR6:  adapter.register_module_tools("progress", coordinator, ["apoch_progress"])
PR7:  adapter.register_module_tools("insights", coordinator, ["apoch_insights"])
PR8:  adapter.register_module_tools("logs", coordinator, ["apoch_logs"])
PR9:  adapter.register_module_tools("legacy", coordinator, legacy_aliases)
```

## ADR-002: Contrato Unificado de Respuestas

**Decisión**: Dataclass base `ToolResponse` en `apoch/public_api/models.py`. Toda herramienta pública devuelve una instancia serializada a dict.

```python
@dataclass
class ToolResponse:
    api_version: str = "1.0"       # Siempre primer campo
    summary: str                    # Una línea con la respuesta principal
    explanation: str                # Contexto breve
    evidence: list[EvidenceSource]  # Datos o hechos que respaldan
    suggested_action: str | None    # Qué hacer con la info (None si no aplica)
    confidence: float               # 0.00–1.00
    generated_at: str               # ISO 8601
    data_freshness: int             # Segundos desde recolección
    metadata: dict                  # Reservado para extensibilidad
```

Cada tool extiende mínimamente (ej. `RecommendResponse` con `priority`, `expected_benefit`). El envelope de respuesta MCP usa el formato existente:

```json
{"version": 1, "ok": true, "data": { <ToolResponse como dict> }}
```

## ADR-003: Modelo de Evidencia y Confianza

**Decisión**: `EvidenceSource` en `apoch/public_api/models.py`. Cada módulo consultado aporta un evidence source.

```python
@dataclass
class EvidenceSource:
    source: str        # "Vision", "Guardian", "Chronicle", "Oracle", "Pulse", "Optimizer"
    confidence: float  # 0.00–1.00
    collected_ago: int # Segundos desde que se recolectó
    based_on: str      # Descripción de la fuente (ej. "38 work units", "diagnostics")
```

**Cálculo de confidence global**: Promedio ponderado de los evidence sources disponibles. Si un módulo timeout, no contribuye y baja el promedio. Mapeo a etiquetas:

| Rango | Etiqueta |
|-------|----------|
| 0.90–1.00 | VERY_HIGH |
| 0.75–0.89 | HIGH |
| 0.50–0.74 | MEDIUM |
| 0.25–0.49 | LOW |
| 0.00–0.24 | VERY_LOW |

Herramientas Public Stable aceptan `confidence` como número (`0.00`–`1.00`) y opcionalmente como etiqueta.

## ADR-004: Timeouts, Degradación y Resiliencia

**Decisión**: Timeout por módulo usando `asyncio.wait_for()`. Si un módulo no responde, la tool continúa con los datos disponibles y reduce confidence.

```
apoch_status
  │
  ├── Vision [timeout 1.0s] ───→ ⏱️ no responde
  ├── Guardian [timeout 0.5s] ──→ ✅ datos disponibles
  ├── Chronicle [timeout 0.5s] ─→ ✅ datos disponibles
  └── Oracle [timeout 1.0s] ────→ ⏱️ no responde
       │
       ▼
  Evidence: [Guardian, Chronicle]
  Confidence: MEDIUM (parcial)
  Summary: "🟡 Sistema funcionando con limitaciones"
  No fatal error — respuesta completa
```

**Principios**:
- La API nunca crashea por fallo de un módulo
- Toda respuesta incluye qué datos estuvieron disponibles (evidence)
- Confidence refleja completitud de datos
- Si NINGÚN módulo responde → `ERR_TIMEOUT` con código del catálogo

**Códigos de error** (catálogo global del spec):

| Código | Condición |
|--------|-----------|
| `ERR_TIMEOUT` | Todos los módulos timeout |
| `ERR_NO_DATA` | Módulos responden pero sin datos |
| `ERR_NOT_INITIALIZED` | Sistema no arrancado |
| `ERR_DEPENDENCY_UNAVAILABLE` | Módulo requerido no cargado |
| `ERR_INVALID_ARGUMENT` | Parámetro inválido |
| `ERR_INTERNAL` | Error interno inesperado |
| `ERR_UNKNOWN` | No clasificado |

## ADR-005: Versionado de la API

**Decisión**: MAJOR.MINOR en constante `API_VERSION` en `apoch/public_api/version.py`.

```
# apoch/public_api/version.py
API_VERSION = "1.0"
```

| Cambio | Incremento |
|--------|-----------|
| Breaking: eliminar/modificar campo obligatorio | MAJOR |
| Breaking: cambiar semántica de respuesta | MAJOR |
| Compatible: añadir campo opcional | MINOR |
| Compatible: nuevo evidence source | MINOR |

`api_version` viaja en toda respuesta como primer campo. `ToolResponse.api_version` se establece desde la constante. Los clientes pueden detectar cambios automáticamente.

## ADR-006: Backward Compatibility

**Decisión**: Estrategia de tres fases con aliases directos, deprecación progresiva y eliminación programada.

### Fase 1 — Alias directo (convivencia)

Cada tool legacy se registra como **alias** que apunta al mismo handler MCP del coordinator. Sin transformación de respuesta.

```
FastMCP registry:
  vision_state        ──→ alias ──→ ApochCoordinator.status
  chronicle_query     ──→ alias ──→ ApochCoordinator.history
  guardian_diagnostics ──→ alias ──→ ApochCoordinator.health
  guardian_all_diagnostics ──→ alias ──→ ApochCoordinator.health
  vision_logs         ──→ alias ──→ ApochCoordinator.logs
```

**Contrato**: el alias recibe los mismos argumentos y devuelve exactamente el mismo formato de respuesta que la tool original (ToolResponse → dict legacy equivalente). No hay cambios visibles para el cliente.

### Fase 2 — Deprecación

Las tools legacy se marcan como `deprecated` en su descripción MCP. El campo `metadata` de la respuesta incluye:

```json
{"legacy_tool": "vision_state", "replaced_by": "apoch_status", "deprecated_since": "1.0"}
```

Los agentes OpenCode ven un warning no bloqueante. El handler sigue siendo el mismo alias.

### Fase 3 — Eliminación

Las tools legacy se eliminan del registro MCP después de:

| Evento | Plazo |
|--------|-------|
| Release que introduce nuevas tools | +1 MAJOR version |
| Aviso de deprecación | No antes de 2 releases |
| Fecha mínima de vida | 90 días desde Fase 1 |

**Rollback**: Revertir la eliminación de aliases es un cambio de una línea en el registro.

### Mapa completo de migración

| Tool legacy | Reemplazo | Alias | Deprecación | Eliminación |
|-------------|-----------|-------|-------------|-------------|
| `vision_state` | `apoch_status` | Directo | v1.1 | v2.0 |
| `chronicle_query` | `apoch_history` | Directo | v1.1 | v2.0 |
| `guardian_diagnostics` | `apoch_health` | Directo | v1.1 | v2.0 |
| `guardian_all_diagnostics` | `apoch_health` | Directo (fusionado) | v1.1 | v2.0 |
| `vision_logs` | `apoch_logs` | Directo | v1.1 | v2.0 |
| `vision_config` | 🔒 Internal | Sin alias | v1.0 | v1.0 |
| `chronicle_record` | 🔒 Internal | Sin alias | v1.0 | v1.0 |
| `chronicle_stats` | ⚡ Advanced | Sin alias | v1.0 | v1.0 |
| `guardian_clear_*` | 🔄 Automática | Sin alias | v1.0 | v1.0 |
| `vision_system` | 🗑️ Eliminar | Sin alias | v1.0 | v1.0 |

## ADR-007: Política de Concurrencia

**Decisión**: `asyncio.gather()` con `return_exceptions=True`, timeouts individuales por módulo, sin timeout global, sin cancelación entre módulos. Orden de resolución indeterminado (depende del scheduler de asyncio).

```python
async def _query_modules(
    self,
    queries: list[tuple[str, Coroutine, float]],  # (name, coro, timeout_s)
) -> dict[str, Any]:
    """Ejecuta N consultas a módulos en paralelo con timeouts individuales.

    - Cada módulo tiene su propio timeout (asyncio.wait_for).
    - Los módulos que exceden el timeout no cancelan a los demás.
    - return_exceptions=True: timeout/excepción = módulo no disponible.
    - No hay timeout global: los módulos lentos no aceleran a los rápidos.
    - Orden de resolución: indeterminado (asyncio scheduler).
    """
    results: dict[str, Any] = {}

    async def _query_one(name: str, coro: Coroutine, timeout: float) -> None:
        try:
            results[name] = await asyncio.wait_for(coro, timeout=timeout)
        except (asyncio.TimeoutError, Exception):
            results[name] = None  # Módulo no disponible

    tasks = [_query_one(name, coro, timeout) for name, coro, timeout in queries]
    await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### Reglas

| Aspecto | Decisión |
|---------|----------|
| Timeout por módulo | `asyncio.wait_for()` con segundos por servicio |
| Timeout global | No. Módulos lentos no afectan a los rápidos. |
| Cancelación entre módulos | No. Un timeout no cancela a los demás. |
| Orden de resolución | Indeterminado. No depende del orden de `gather()`. |
| Prioridad entre módulos | No hay. Todos los módulos tienen igual prioridad. |
| Error en un módulo | `None` en results. No propaga excepción. |
| Todos los módulos fallan | El método responde con `ERR_TIMEOUT` y confidence LOW. |

### Prioridad entre módulos

No existe prioridad explícita. Si dos módulos pueden responder la misma pregunta (ej. Vision y Guardian para estado), el que responda primero se usa; si el más lento también responde, ambos aparecen en `evidence[]`. La tool decide cómo combinar fuentes duplicadas.

## Non-Goals

1. **No ejecutar acciones automáticamente.** Herramientas públicas son de consulta. Nunca modifican estado.
2. **No modificar configuración.** No hay tools públicas para cambiar config de Apoch-AI.
3. **No escribir en Chronicle desde tools públicas.** `chronicle_record` es Internal.
4. **No exponer módulos internos.** Ninguna tool revela Vision, Guardian, Chronicle, Pulse, Optimizer ni Oracle.
5. **No depender del orden de ejecución interno.** La implementación puede cambiar el orden de consulta.
6. **No mantener estado entre llamadas MCP.** Cada llamada es independiente.
7. **No romper compatibilidad Public Stable.** Cambios solo en Experimental y Advanced.
8. **No crear herramientas sin acceptance matrix.** Toda tool nueva pasa los 7 criterios.
9. **No registrar herramientas incompletas.** El registro MCP ocurre solo cuando la implementación está completa. Sin stubs visibles. Sin ERR_NOT_IMPLEMENTED público.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/apoch/public_api/__init__.py` | Create | Paquete de API pública |
| `src/apoch/public_api/models.py` | Create | ToolResponse, EvidenceSource, RecommendResponse, ErrorResponse |
| `src/apoch/public_api/coordinator.py` | Create | ApochCoordinator: 7 herramientas con contrato completo |
| `src/apoch/public_api/registry.py` | Create | ServiceRegistry tipado con los 6 módulos |
| `src/apoch/public_api/metrics.py` | Create | CallMetrics para monitoreo interno |
| `src/apoch/public_api/version.py` | Create | Constante API_VERSION |
| `src/apoch/public_api/errors.py` | Create | Códigos de error del catálogo global |
| `src/apoch/adapters/manager.py` | Modify | AgentAdapterManager construye ServiceRegistry e inyecta Coordinator. Sin registro de tools nuevas (registro progresivo: cada PR registra la suya). |
| `src/apoch/adapters/opencode/server.py` | Modify | Opción para alias de tools legacy |
| `src/apoch/modules/vision/module.py` | Modify | Eliminar `get_tool_defs()` — vision_state/logs/system pasan a coordinator |
| `src/apoch/modules/chronicle/module.py` | Modify | Eliminar `get_tool_defs()` — chronicle_query/stats pasan a coordinator |
| `src/apoch/modules/guardian/module.py` | Modify | Eliminar `get_tool_defs()` — guardian_diagnostics pasan a coordinator |
| Varios test files | Modify | Actualizar tests para nuevo patrón |

## Data Flow

```
MCP Call: apoch_recommend({})
    │
    ▼
FastMCP gateway ──→ OpenCodeAdapter._dispatch("apoch_recommend", {})
    │                         │
    │                  valida JSON Schema
    │                         │
    ▼                         ▼
ApochCoordinator.recommend()
    │
    ├── asyncio.gather(
    │     timeout(Oracle.hypotheses, 2.0s),
    │     timeout(Guardian.diagnostics, 0.5s),
    │     timeout(Vision.module_state, 0.5s),
    │     timeout(Pulse.measurements, 0.5s),
    │   return_exceptions=True)
    │
    ├── Filtrar timeouts/errores
    ├── Construir EvidenceSource[] por módulo respondedor
    ├── Calcular confidence global
    └── Ensamblar ToolResponse → dict
         │
         ▼
    {"version":1, "ok":true, "data": {
      "api_version": "1.0",
      "summary": "...",
      "evidence": [...],
      "confidence": 0.85,
      ...
    }}
```

## Interfaces / Contracts

```python
# apoch/public_api/models.py

@dataclass
class EvidenceSource:
    source: str
    confidence: float        # 0.00-1.00
    collected_ago: int       # segundos
    based_on: str

@dataclass
class ToolResponse:
    api_version: str = "1.0"
    summary: str
    explanation: str
    evidence: list[EvidenceSource]
    suggested_action: str | None = None
    confidence: float = 0.0
    generated_at: str = ""   # ISO 8601; se setea en construcción
    data_freshness: int = 0
    metadata: dict = field(default_factory=dict)

@dataclass
class RecommendResponse(ToolResponse):
    priority: str = "MEDIUM"        # HIGH | MEDIUM | LOW
    expected_benefit: str | None = None

@dataclass
class ErrorResponse:
    ok: bool = False
    error: dict = field(default_factory=dict)  # {code, message}
```

```python
# apoch/public_api/registry.py

@dataclass
class ServiceRegistry:
    """Servicios disponibles para el coordinator.

    None = módulo no cargado. Cada tool decide si el módulo es
    requerido u opcional en su contrato (ver ApochCoordinator).
    """
    vision: "VisionModule | None" = None
    chronicle: "ChronicleModule | None" = None
    guardian: "GuardianModule | None" = None
    pulse: "PulseModule | None" = None
    optimizer: "OptimizerModule | None" = None
    oracle: "OracleModule | None" = None


# apoch/public_api/metrics.py

@dataclass
class CallMetrics:
    tool: str
    modules_consulted: list[str]
    modules_succeeded: list[str]
    modules_failed: list[str]
    time_per_module: dict[str, float]
    total_time: float
    confidence_final: float
    evidence_count: int
    timestamp: str
    error_code: str | None = None
```

```python
# apoch/public_api/coordinator.py

class ApochCoordinator:
    """Coordina módulos internos para producir respuestas de herramientas públicas.

    7 métodos públicos, cada uno orquesta, agrega y devuelve ToolResponse.
    Sin estado entre llamadas. Todos los timeouts en segundos.
    """

    def __init__(self, services: ServiceRegistry, metrics: CoordinatorMetrics) -> None:
        self._services = services
        self._metrics = metrics
        self._timeouts = {
            "vision": 1.0, "guardian": 0.5, "chronicle": 0.5,
            "oracle": 2.0, "pulse": 0.5, "optimizer": 1.0,
        }

    # ─── Contrato del Coordinator ──────────────────────────────

    async def status(self) -> ToolResponse:
        """Vista general del sistema.

        Entradas:   Ninguna.
        Salida:     ToolResponse con estado general, componentes activos,
                    problemas detectados, actividad reciente, recomendación rápida.
        Módulos:    Vision, Guardian, Chronicle, Oracle.
        Timeouts:   Vision(1s), Guardian(0.5s), Chronicle(0.5s), Oracle(2s).
        Fallo:      Si algún módulo timeout, responde con datos parciales.
                    Si TODOS fallan → ERR_TIMEOUT.
        Evidencia:  1+ source requerido para respuesta completa.
                    0 sources → ERR_TIMEOUT.
        """

    async def history(self, horas: int | None = None,
                      tipo: str | None = None) -> ToolResponse:
        """Línea de tiempo cronológica legible.

        Entradas:   horas (opcional, últimas N horas),
                    tipo (opcional, lifecycle|tool|error).
        Salida:     ToolResponse con narrativa cronológica descendente.
        Módulos:    Chronicle, Vision.
        Timeouts:   Chronicle(0.5s), Vision(0.5s).
        Fallo:      Chronicle timeout → ERR_DEPENDENCY_UNAVAILABLE.
                    Vision timeout → respuesta solo con Chronicle.
        Evidencia:  Chronicle requerido. Vision opcional.
        """

    async def health(self) -> ToolResponse:
        """Diagnóstico interpretado con clasificación 🟢/🟡/🔴.

        Entradas:   Ninguna.
        Salida:     ToolResponse con clasificación y problemas detallados.
        Módulos:    Guardian, Vision.
        Timeouts:   Guardian(0.5s), Vision(0.5s).
        Fallo:      Guardian timeout → ERR_DEPENDENCY_UNAVAILABLE.
                    Vision timeout → respuesta solo con Guardian.
        Evidencia:  Guardian requerido. Vision opcional.
        """

    async def recommend(self) -> RecommendResponse:
        """Siguiente acción de mayor impacto.

        Entradas:   Ninguna (usa estado actual autónomamente).
        Salida:     RecommendResponse con Next Action, Why, Priority.
        Módulos:    Oracle, Optimizer, Pulse, Guardian, Vision.
        Timeouts:   Oracle(2s), Optimizer(1s), Pulse(0.5s),
                    Guardian(0.5s), Vision(0.5s).
        Fallo:      Degrada gracefulmente: usa módulos disponibles y baja
                    confidence. No expone qué módulo falló.
        Evidencia:  1+ source. 0 sources → ERR_TIMEOUT con confidence LOW.
        """

    async def progress(self, periodo: str | None = None) -> ToolResponse:
        """Productividad, evolución y tendencias interpretadas.

        Entradas:   periodo (opcional, hoy|semana|mes).
        Salida:     ToolResponse con resumen de productividad y tendencias.
        Módulos:    Pulse.
        Timeouts:   Pulse(0.5s).
        Fallo:      Pulse timeout o no disponible → ERR_DEPENDENCY_UNAVAILABLE.
        Evidencia:  Pulse requerido.
        """

    async def insights(self) -> ToolResponse:
        """Patrones detectados y oportunidades de mejora.

        Entradas:   Ninguna.
        Salida:     ToolResponse con patrones y oportunidades.
        Módulos:    Optimizer, Pulse.
        Timeouts:   Optimizer(1s), Pulse(0.5s).
        Fallo:      Optimizer timeout → ERR_DEPENDENCY_UNAVAILABLE.
                    Pulse timeout → respuesta solo con Optimizer.
        Evidencia:  Optimizer requerido. Pulse opcional.
        """

    async def logs(self, nivel: str | None = None,
                   limite: int | None = 50,
                   modulo: str | None = None) -> ToolResponse:
        """Logs técnicos del sistema para depuración.

        Entradas:   nivel (opcional, INFO|WARN|ERROR|FATAL),
                    limite (opcional, default 50),
                    modulo (opcional).
        Salida:     ToolResponse con entradas de log formateadas.
        Módulos:    Vision.
        Timeouts:   Vision(0.5s).
        Fallo:      Vision timeout → ERR_DEPENDENCY_UNAVAILABLE.
        Evidencia:  Vision requerido.
        """
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `ToolResponse` serialization, `EvidenceSource`, `ServiceRegistry`, confidence calc | Dataclass + fixture tests |
| Unit | `CallMetrics` recording | Mock Chronicle, verify event shape |
| Unit | Coordinator per-tool orchestration | Mock `ServiceRegistry` + asyncio |
| Integration | Module timeouts → graceful degradation | Mock con `asyncio.sleep` que excede timeout |
| Integration | Error code mapping | Simular cada condición de error del catálogo |
| Integration | Alias legacy → mismo handler que tool nueva | FastMCP: misma función registrada con dos nombres |
| Resilience | 1 de N módulos timeout → confidence correcta | Test parametrizado: N-1 módulos OK, 1 timeout |
| Resilience | Todos los módulos timeout → ERR_TIMEOUT | Mock con todos los servicios lentos |

## Métricas Internas del Coordinador

No expuestas por MCP. Registradas internamente para evaluar rendimiento de la API pública.

```python
@dataclass
class CallMetrics:
    tool: str                              # "apoch_status", "apoch_recommend", etc.
    modules_consulted: list[str]            # ["vision", "guardian", ...]
    modules_succeeded: list[str]            # Respondieron dentro del timeout
    modules_failed: list[str]              # Timeout o error
    time_per_module: dict[str, float]      # Segundos por módulo
    total_time: float                      # Tiempo total de la llamada
    confidence_final: float                # Confidence resultante
    evidence_count: int                    # N fuentes de evidencia
    timestamp: str                         # ISO 8601
    error_code: str | None = None          # Si la tool respondió con error
```

**Almacenamiento**: Evento en Chronicle (fuera del flujo MCP). Cada `CallMetrics` se registra después de responder al cliente, sin bloquear la respuesta.

**Uso**: Dashboard interno para detectar degradación de módulos, timeouts frecuentes, confianza sistemáticamente baja. Permite decidir si un módulo necesita optimización o si un timeout debe ajustarse.

## Migration / Rollout

1. **Fase 1**: Crear `apoch/public_api/` con coordinator y modelos. Coordinator registrado como herramienta adicional (conviven tools viejas y nuevas).
2. **Fase 2**: Tools legacy se marcan como `deprecated` en descripción. Coordinator se convierte en el registro principal.
3. **Fase 3**: Se eliminan `get_tool_defs()` de módulos. Tools legacy redirigen a coordinator.
4. **Rollback**: Revertir registro de coordinator; módulos recuperan `get_tool_defs()`.

## Open Questions

- [ ] ¿Timeouts configurables por el usuario (vía config) o fijos en código para la primera versión?
- [ ] ¿`apoch_recommend` debe incluir Expected Benefit desde el diseño inicial o agregarse en MINOR posterior?
- [ ] ¿ServiceRegistry debe expirar módulos no disponibles o simplemente mantener referencia None?
