# LLM-Assisted Source Selection Tasks

## Phase 1: Specification

- [x] Audit current discovery, policy, Autopilot, and regression contracts.
- [x] Record the two-layer policy, LLM boundary, fallback, and test cases.
- [ ] Commit the specification.

## Phase 2: Candidate Assessment

- [ ] Add bounded candidate assessment domain types and strict response validation.
- [ ] Add OpenAI-compatible batch assessor and configuration.
- [ ] Add deterministic ranking fallback with explicit status.
- [ ] Add focused tests for valid, invalid, unavailable, and low-confidence results.

## Phase 3: Workflow And UX

- [ ] Limit legal queues to six candidates while retaining usable fallbacks.
- [ ] Add one validated supplemental search round for normal learning scopes.
- [ ] Preserve direct-authority gate for service workflows.
- [ ] Persist assessment/supplemental-search state and render distinct recovery copy.
- [ ] Commit implementation after targeted tests.

## Phase 4: Regression And Audit

- [ ] Add recorded self-media, travel-agent, and service-workflow cases.
- [ ] Extend deterministic E2E and Playwright coverage.
- [ ] Run fast, E2E, browser, and isolated live checks.
- [ ] Complete the requirement-by-requirement audit and commit verification.

