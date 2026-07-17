# Project Intake Clarification

## Problem

Creating a domain project currently treats every input as equally clear. Ambiguous names such as `Agent`, broad scopes such as `AI`, and conflicting learning level/goal pairs can send search and curriculum generation down the wrong path. Conversely, missing goals should not block a learner from starting.

## Scope

- Evaluate project intake locally and deterministically before final navigation.
- Ask one focused clarification only when the result changes search or learning boundaries.
- Persist confirmed scope, assumptions, and an intake state on `DomainProject`.
- Let a learner select a recommendation, write a custom boundary, or accept the default interpretation.
- Surface the confirmed boundary and assumptions on the dashboard.

## Decision rules

Priority is: named ambiguity, overly broad scope, learning-level conflict, then no clarification. A missing goal uses the default goal `建立可溯源的入门领域地图` and records that assumption without asking another question.

## Non-goals

- No LLM call, login, automatic search, or automatic build during intake.
- No multi-turn chat or unrestricted questionnaire.

## Acceptance criteria

1. Clear input creates a confirmed project and goes directly to its dashboard.
2. Ambiguous, broad, or conflicting input creates a `needs_clarification` project and opens one focused confirmation page.
3. Recommendation, custom text, and default continuation all result in a confirmed project with persisted metadata.
4. Existing projects remain readable as confirmed projects.
5. Desktop and mobile flows are browser-regression covered.
