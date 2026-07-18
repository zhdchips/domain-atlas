# Regional Official Discovery Plan

1. Extend deterministic source assessment with target-region inference,
   brand-aligned-domain checks, direct-source eligibility, and structured
   terminal conditions.
2. Add a bounded official-entry inspector behind a protocol. It receives only
   brand-aligned first-party candidates, extracts regional links from returned
   HTML, and writes provenance into candidate metadata. Its HTTP implementation
   uses short timeouts and never turns a failed inspection into a false positive.
3. In Guided Autopilot, run ordinary search, one general official query, then at
   most one regional query. Assess, inspect, persist, and select only ingestible
   matching evidence. Record query and evidence outcomes in workflow steps.
4. Render region/entry provenance and distinct recovery states in the dashboard
   and workflow status partial without duplicating the same terminal error.
5. Add fixture-based tests for the Sushiro scenario, a third-party H5 negative
   case, and Playwright rendering. Run the relevant regression layers and an
   isolated live compatibility check when providers are available.

## Design Decisions

- `official_entry` is evidence about where to continue, not proof that the
  linked social/app endpoint is readable or belongs to the operator.
- Domain matching is deliberately narrow: the brand token must occur in the
  registrable domain, not merely a subdomain, title, or snippet.
- Region matching is separate from authority role. A source can be official and
  still be ineligible for automatic use in a different regional workflow.
- The resolver is injectable so deterministic tests do not depend on network
  access or a real search ranking.
