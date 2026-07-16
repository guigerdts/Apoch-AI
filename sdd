SDD Change Request — Rediseño de la API Pública MCP de Apoch-AI

Contexto

Después de completar la auditoría técnica, corregir los bloqueantes críticos, validar la integración con OpenCode y verificar el funcionamiento end-to-end del sistema, se identificó una oportunidad importante de mejora.

La arquitectura interna de Apoch-AI está correctamente separada en módulos especializados:

- Vision
- Chronicle
- Guardian
- Pulse
- Optimizer
- Oracle

Desde el punto de vista de ingeniería esta división es correcta.

Sin embargo, desde la perspectiva del usuario final, la API MCP continúa exponiendo demasiados conceptos internos.

El usuario no debería tener que conocer cómo está construido el sistema para poder utilizarlo.

La interfaz pública debe representar las necesidades del usuario, no la arquitectura del software.

---

Objetivo

Rediseñar completamente la superficie pública de herramientas MCP.

No se trata únicamente de renombrar herramientas.

Se debe replantear toda la experiencia de uso siguiendo principios de UX, API Design, Human-Centered Design y SDD.

El resultado esperado es una API extremadamente intuitiva donde cualquier persona pueda descubrir las capacidades del sistema sin leer documentación técnica.

---

Filosofía

La arquitectura interna continúa existiendo.

Los módulos siguen teniendo exactamente las mismas responsabilidades.

No se eliminan.

No se fusionan.

No cambian sus responsabilidades.

Lo único que cambia es la interfaz pública.

La interfaz pública deja de estar diseñada desde los módulos y pasa a estar diseñada desde las preguntas humanas.

El usuario nunca debería pensar:

- ¿Debo llamar Vision?
- ¿Necesito Chronicle?
- ¿Optimizer tiene esta información?
- ¿Guardian sabe esto?

El usuario solamente debería pensar:

- ¿Qué está pasando?
- ¿Qué pasó?
- ¿Hay algún problema?
- ¿Qué debería hacer?
- ¿Cómo voy?
- ¿Cómo puedo mejorar?

Todo el trabajo de coordinar módulos pertenece al sistema, nunca al usuario.

---

Principio Fundamental

Una herramienta MCP representa una intención humana.

Nunca representa un módulo interno.

Nunca representa una implementación.

Nunca representa una clase.

Nunca representa una base de datos.

Nunca representa un servicio.

Nunca representa una arquitectura.

Las herramientas públicas responden preguntas.

Los módulos producen conocimiento.

Las herramientas únicamente entregan ese conocimiento.

---

Regla de Oro

Si para entender una herramienta el usuario necesita conocer:

- Vision
- Guardian
- Chronicle
- Pulse
- Optimizer
- Oracle

entonces esa herramienta está mal diseñada.

El usuario nunca debería aprender la arquitectura interna.

---

Principio de Abstracción

Oracle puede consultar:

- Vision
- Pulse
- Guardian
- Chronicle
- Optimizer

Pero el usuario nunca debería saberlo.

Guardian puede consultar Chronicle.

Optimizer puede consumir Pulse.

Vision puede alimentar Oracle.

Nada de eso pertenece a la interfaz pública.

Toda esa comunicación permanece interna.

---

Regla de los 30 segundos (obligatoria)

Toda nueva herramienta deberá superar esta validación.

Una persona que jamás utilizó Apoch-AI debe poder comprender:

- qué hace
- cuándo utilizarla
- qué información devuelve

únicamente leyendo:

- el nombre
- la descripción de una línea

Si necesita conocer la arquitectura interna para entenderla, la herramienta debe rechazarse.

Esta regla es obligatoria para futuras contribuciones.

---

Nueva clasificación

Las herramientas dejan de agruparse por módulo.

Ahora se agrupan por intención humana.

---

1. apoch_status

Pregunta que responde

«¿Qué está pasando?»

Debe convertirse en el panel principal del sistema.

No debe limitarse a responder "Healthy".

Debe construir un resumen inteligente.

Debe combinar información proveniente de todos los módulos relevantes.

Ejemplo:

- estado general
- componentes activos
- problemas detectados
- actividad reciente
- última ejecución
- recomendación rápida

El usuario debe entender el estado del sistema en menos de cinco segundos.

No debe exponer:

- PID
- RAM
- Threads
- procesos internos
- objetos Python

Todo eso pertenece al modo desarrollador.

---

2. apoch_history

Pregunta que responde

«¿Qué pasó?»

No debe devolver registros SQLite.

No debe devolver filas.

No debe devolver estructuras técnicas.

Debe construir una narrativa cronológica.

Ejemplo:

09:10 Inicio del análisis.

09:15 Vision detectó una nueva configuración.

09:18 Optimizer generó tres hipótesis.

09:22 Guardian detectó una advertencia.

09:24 Guardian recuperó automáticamente el sistema.

09:26 Oracle actualizó las recomendaciones.

Debe parecer una historia de lo ocurrido.

No una consulta SQL.

---

3. apoch_health

Pregunta que responde

«¿Tengo algún problema?»

Debe clasificar automáticamente la severidad.

Por ejemplo:

🟢 Sin problemas

🟡 Advertencias

🔴 Problemas críticos

Cada problema debe incluir:

- impacto
- explicación
- posible causa
- acción recomendada

No debe obligar al usuario a interpretar diagnósticos técnicos.

---

4. apoch_recommend

Esta debe convertirse en la herramienta más importante del sistema.

No debe limitarse a mostrar recomendaciones generadas por Oracle.

Debe convertirse en el copiloto principal.

Puede consultar cualquier módulo necesario.

Debe responder:

¿Qué debería hacer ahora?

La respuesta puede incluir:

- siguiente acción
- prioridad
- riesgos
- oportunidades
- explicación
- beneficio esperado
- acciones concretas

La coordinación entre módulos es completamente transparente.

---

5. apoch_progress

(Se propone reemplazar el nombre apoch_metrics)

La palabra "metrics" describe una implementación.

"Progress" responde una pregunta humana.

Pregunta:

¿Cómo voy?

Debe resumir:

- productividad
- evolución
- progreso
- actividad
- tendencias generales

No debe mostrar únicamente números.

Debe interpretar los datos.

---

6. apoch_insights

(Se propone reemplazar apoch_optimize)

La palabra "optimize" sugiere ejecutar cambios.

La herramienta realmente entrega oportunidades de mejora.

"Insights" comunica mucho mejor su propósito.

Pregunta:

¿Cómo puedo mejorar?

Debe responder con:

- oportunidades
- patrones detectados
- hipótesis
- sugerencias
- posibles optimizaciones

No ejecuta cambios.

No modifica el sistema.

Solo entrega conocimiento accionable.

---

7. apoch_logs

Única herramienta orientada a desarrolladores.

Debe permanecer como herramienta avanzada.

Su propósito es facilitar debugging.

Nunca debería ser la herramienta principal para usuarios normales.

---

Herramientas internas

Las siguientes herramientas no deben exponerse como API pública.

Su responsabilidad pasa a ser exclusivamente interna.

Vision

Chronicle

Guardian

Pulse

Optimizer

Oracle

Sus funciones continúan existiendo.

Simplemente dejan de formar parte de la experiencia pública.

La comunicación entre ellas ocurre mediante llamadas internas.

---

Principios adicionales

Ocultar implementación

Una API pública nunca debe revelar:

- clases
- módulos
- archivos
- procesos
- bases de datos
- nombres internos

Debe hablar únicamente en términos de valor para el usuario.

---

Respuestas interpretadas

Siempre que sea posible la respuesta debe interpretar los datos.

No devolver solamente información.

Debe explicar qué significa.

Debe ayudar a decidir.

---

Una herramienta = una intención

Una herramienta no representa un módulo.

Representa una necesidad concreta del usuario.

---

Independencia

Cada herramienta debe aportar valor por sí sola.

Ninguna debe depender conceptualmente de otra.

Pueden compartir datos internamente.

Pero desde la experiencia del usuario deben sentirse completamente independientes.

Si una herramienta solo existe para complementar otra, probablemente ambas deban fusionarse o replantearse.

---

Criterios obligatorios de aceptación

Toda herramienta pública deberá aprobar los siguientes siete criterios:

1. Responde una pregunta humana claramente identificable.

2. Su nombre es comprensible sin conocer la arquitectura interna.

3. Aporta valor de manera independiente.

4. Oculta completamente la implementación.

5. Devuelve información interpretada, no datos crudos.

6. El usuario sabe cuándo utilizarla únicamente leyendo su descripción.

7. Un usuario nuevo puede utilizarla correctamente en menos de treinta segundos.

Si alguno de estos criterios falla, la herramienta no debe incorporarse a la API pública.

---

Entregables esperados

Esta fase NO implementará código.

Debe generar:

1. Specification SDD completa para las siete herramientas públicas.

2. Contrato funcional de cada herramienta.

3. Entradas y salidas esperadas.

4. Casos de uso reales.

5. Casos límite.

6. Criterios de aceptación.

7. Plan de migración desde las herramientas actuales.

8. Matriz de compatibilidad hacia atrás (Backward Compatibility).

9. Riesgos técnicos.

10. Estrategia de validación.

Todo deberá quedar archivado como artefacto SDD para futuras auditorías y trazabilidad.

---

Resultado esperado

Al finalizar esta especificación, Apoch-AI deberá ofrecer una API MCP que cualquier usuario pueda descubrir y utilizar de forma intuitiva, sin conocer absolutamente nada sobre su arquitectura interna.

La interfaz pública debe responder preguntas humanas.

La arquitectura debe permanecer completamente oculta.

Ese será el criterio principal para aceptar o rechazar cualquier herramienta pública futura.
