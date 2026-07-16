# SDD Proposal — Rediseño de las herramientas MCP de Apoch-AI

## Contexto

Vamos a detener cualquier implementación relacionada con nuevas herramientas MCP para realizar primero un proceso de diseño siguiendo Spec-Driven Development (OpenSpec).

NO quiero modificar código todavía.

NO quiero generar tareas.

NO quiero implementar nada.

Primero debemos cuestionar el diseño actual y verificar si realmente aporta valor al usuario final.

Este trabajo debe terminar como una propuesta formal de OpenSpec, para que quede documentada, revisada y archivada antes de cualquier implementación.

---

# Objetivo

Reevaluar completamente la interfaz pública (MCP Tools) de Apoch-AI.

No debemos partir de la implementación existente.

Debemos partir del usuario.

La pregunta principal es:

> "Si un desarrollador estuviera usando OpenCode durante varias horas, ¿qué herramientas le resultarían realmente útiles y cuáles jamás utilizaría?"

---

# Filosofía del rediseño

PROJECT_MASTER.md establece que Apoch-AI existe para mejorar la experiencia del agente, no para añadir complejidad.

Por lo tanto:

Las herramientas MCP NO deben diseñarse desde la arquitectura interna.

Deben diseñarse desde las necesidades reales del usuario.

Quiero que cuestiones absolutamente todo.

No des por correcto el diseño actual solamente porque ya existe.

---

# Principio Fundamental

Cada módulo debe aportar valor por sí mismo.

Eso significa:

✓ Chronicle debe ser útil aunque Oracle no exista.

✓ Pulse debe ser útil aunque Optimizer no exista.

✓ Guardian debe ser útil aunque Vision no exista.

✓ Oracle debe ser útil aunque Chronicle esté deshabilitado.

✓ Vision debe ser útil por sí solo.

✓ Optimizer debe generar valor sin depender de otros módulos.

Los módulos podrán compartir información internamente.

Pero NUNCA deberán depender funcionalmente unos de otros para justificar su existencia.

Si un módulo necesita otro para ser útil, entonces su diseño debe replantearse.

---

# Cambio de enfoque

Actualmente muchas herramientas parecen diseñadas desde el código.

Ejemplos:

- optimizer_status
- optimizer_baselines
- pulse_record
- oracle_status

Esos nombres describen implementación.

No describen valor.

Quiero cambiar completamente esa filosofía.

Las herramientas deben responder preguntas humanas.

Por ejemplo:

- ¿Qué hice hoy?
- ¿Qué cambió?
- ¿Cómo voy?
- ¿Qué riesgo tengo?
- ¿Qué debería hacer ahora?
- ¿Qué puedo mejorar?
- ¿Qué aprendí?
- ¿Qué está haciendo Apoch?

Si una herramienta no responde una necesidad real del usuario, probablemente no debería existir como herramienta pública.

---

# Tipos de usuario que deben evaluarse

No diseñes solamente para desarrolladores senior.

Debes analizar al menos estos perfiles.

## Perfil 1

Desarrollador experto.

Quiere velocidad.

Quiere automatización.

Quiere información precisa.

No quiere ruido.

---

## Perfil 2

Usuario nuevo de agentes CLI.

No conoce MCP.

No conoce OpenCode.

No conoce Apoch.

No sabe qué preguntar.

Necesita descubrir valor sin leer documentación técnica.

---

## Perfil 3

Usuario no programador.

Usa OpenCode como asistente.

No entiende arquitectura.

Solo quiere ayuda práctica.

Las herramientas deben ser intuitivas.

---

# Trabajo esperado

Analiza módulo por módulo.

Para cada uno responde:

## 1.

¿Cuál es el propósito real del módulo?

No copies PROJECT_MASTER.

Interpreta el valor real.

---

## 2.

¿Qué problema resuelve?

Debe responder un problema concreto.

No una descripción técnica.

---

## 3.

¿Cuándo un usuario lo usaría?

Debe existir un escenario cotidiano.

No uno artificial.

---

## 4.

¿Cuándo NO debería usarlo?

Esto es igual de importante.

---

## 5.

¿Qué herramientas MCP públicas tendría sentido exponer?

No pienses en el código existente.

Diseña desde cero.

---

## 6.

¿Qué herramientas actuales eliminarías?

Explica por qué.

---

## 7.

¿Qué herramientas nuevas crearías?

Explica el valor.

No solo el nombre.

---

## 8.

¿Qué información debería permanecer interna?

No todo debe exponerse por MCP.

Identifica claramente qué pertenece únicamente a la implementación.

---

# Principios de diseño

Las herramientas públicas deben cumplir lo siguiente.

- Tener nombres comprensibles.
- Ser memorables.
- Expresar intención.
- Resolver una pregunta real.
- Ser útiles por sí mismas.
- Evitar nombres técnicos innecesarios.
- Evitar exponer detalles internos del framework.

---

# Validación

Cada herramienta propuesta deberá responder estas preguntas.

✓ ¿Un usuario sabría cuándo usarla?

✓ ¿El nombre explica claramente qué hace?

✓ ¿Aporta valor sin depender de otro módulo?

✓ ¿Resuelve un problema real?

✓ ¿Evita exponer implementación interna?

Si alguna respuesta es "no", la herramienta debe replantearse.

---

# Entregables OpenSpec

No quiero código.

Quiero artefactos SDD.

Genera únicamente:

1. Proposal

2. Specification

3. Design Rationale

4. Decisiones arquitectónicas

5. Alternativas descartadas

6. Riesgos

7. Compatibilidad hacia atrás

8. Impacto sobre PROJECT_MASTER.md

9. Plan de migración desde las herramientas actuales

10. Criterios de aceptación verificables

---

# Restricciones

No modificar código.

No crear tareas.

No generar PR.

No implementar.

Todo debe finalizar como una propuesta OpenSpec lista para revisión y aprobación.

La implementación solo podrá comenzar después de que esta propuesta sea aprobada explícitamente.
