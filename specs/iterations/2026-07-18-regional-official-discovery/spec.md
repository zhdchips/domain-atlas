# Regional Official Discovery Spec

## Purpose

Improve Guided mode for branded service workflows when a real official regional
entry exists but ordinary web search returns only third-party pages or an
adjacent-region site. The system must discover and explain official entry
evidence without lowering the official-first gate or treating inaccessible
social/app links as crawlable documentation.

## User Problem

For `寿司郎在线取号流程`, ordinary search found a Taiwan site and supplemental
web pages, but missed the brand's Simplified-Chinese official site and its
Guangzhou regional entry. Guided mode reported that no first-party source
existed, which was too strong. Conversely, accepting a Taiwan source or an
unverified H5 page as mainland process evidence would be unsafe.

## Functional Requirements

### Regional Discovery

- For an official-first workflow with no matching direct source after the
  ordinary official query, perform at most one regional official query.
- Determine the target region from the scope when explicit. For Chinese-first
  projects with no conflicting region marker, the bounded fallback region is
  `CN` (China mainland). Taiwan, Hong Kong, and other explicitly named regions
  must not fall back to `CN`.
- The regional query uses the extracted brand/entity plus the target region and
  limited service-entry terms (`官方`, `微信公众号`, `小程序`, `服务规则`, and the
  matching workflow keyword). It must not become an unbounded search loop.

### Official Entry Evidence

- A candidate may be a `first_party` entry when its registrable domain has a
  brand-aligned identity signal. This is a deterministic evidence signal, not a
  legal ownership claim.
- For a small bounded set of such entry candidates, inspect the HTML for links
  to regional official entries. A retained relationship records: discovery URL,
  target URL, target label, region, evidence type, and verification state.
- A regional entry on an official discovery page is `official_entry` evidence.
  A target that is an official crawlable page may be queued as a direct source.
  An external social/app target (for example a WeChat article or mini-program)
  remains non-ingestible until manually confirmed.
- A plain third-party H5, even if its URL or title contains the brand name, is
  never promoted by name matching alone.

### Region And Selection Policy

- Candidate metadata includes `source_region`, `target_region`, and
  `region_match` (`match`, `cross_region`, or `unknown`) where applicable.
- Taiwan, Hong Kong, and other cross-region sources cannot satisfy the direct
  authority requirement for a mainland workflow. They remain visible for
  manual confirmation with a region warning.
- Matching direct official documents may proceed through the existing guided
  queue. An official-entry-only result stops before ingestion with
  `official_entry_requires_confirmation`, not `evidence_insufficient`.
- If the regional target cannot be fetched or its ownership cannot be verified,
  preserve the official-entry provenance and return
  `official_entry_unavailable`; do not silently ingest the discovery page as
  though it documented the requested service flow.

### Learner Feedback

- Candidate cards show source region, official-entry relationship, target
  address, and the reason a candidate was or was not automatically selected.
- Workflow status distinguishes: no official material, cross-region official
  material, official entry needing manual confirmation, and unavailable or
  unverifiable official entry.
- A single terminal recovery message is rendered once per failed workflow step;
  the outer workflow failure must not repeat the same text.

## Non-Goals

- No legal proof of domain ownership, CAPTCHA bypass, mini-program automation,
  or broad crawling of every discovered result.
- No automatic rebuild, migration, or deletion of existing projects.
- No relaxation of Expert/manual confirmation controls.

## Acceptance Criteria

1. A recorded mainland `寿司郎在线取号流程` case performs one regional query,
   retains the official Simplified-Chinese discovery page and its Guangzhou
   entry provenance, and does not classify Taiwan material as mainland direct
   evidence.
2. A trusted official-page external WeChat/app entry remains visible with its
   provenance, is not automatically ingested, and has a clear confirmation
   recovery state.
3. An unverified brand-named third-party H5 cannot pass the official-first
   gate.
4. Existing direct official documents and non-service scopes preserve their
   current selection behavior.
5. Unit, deterministic E2E, and browser regression tests cover no-official,
   cross-region, official-entry, and third-party-H5 cases.
