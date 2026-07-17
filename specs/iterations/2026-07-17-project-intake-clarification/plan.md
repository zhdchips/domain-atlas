# Plan

1. Add backward-compatible project columns: `scope`, `intake_status`, and `intake_metadata_json`.
2. Implement an explainable deterministic intake assessor with profiles for ambiguous terms and broad domains, plus level/goal conflict checks. Keep an optional `IntakeSuggestionProvider` protocol boundary for a future LLM enhancer.
3. Create a single-question clarification page and confirmation action. Save the selected or custom scope and assumptions before entering the dashboard.
4. Display the confirmed boundary and assumptions in the dashboard, and preserve normal HTML form behavior with existing pending enhancement.
5. Add repository/application/browser checks and run the fast and browser regression layers.

## State model

`ready_to_create` is the transient request evaluation state. A project is persisted as either `needs_clarification` or `confirmed`. Existing rows default to `confirmed`, preserving their behavior.
