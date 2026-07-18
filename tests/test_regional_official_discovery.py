from __future__ import annotations

import httpx

from domain_atlas.core.db import initialize_database
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateDraft, SourceCandidateRepository
from domain_atlas.domain.sources import SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.workflow.autopilot import AutopilotWorkflow
from domain_atlas.workflow.official_entries import HttpOfficialEntryInspector
from domain_atlas.workflow.source_policy import build_selection_plan, regional_official_query


class QueryDiscoveryProvider:
    def __init__(self, responses: dict[str, list[SourceCandidateDraft]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        self.calls.append(query)
        return self.responses.get(query, [])


class EntryOnlyInspector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[SourceCandidateDraft]]] = []

    def inspect(self, *, target_region: str, candidates: list[SourceCandidateDraft]):
        self.calls.append((target_region, candidates))
        return [
            SourceCandidateDraft(
                provider="official_entry",
                provider_source_id="official-entry",
                title="广州寿司郎官方服务入口",
                url="https://mp.weixin.qq.com/s/sushiro-guangzhou",
                snippet="fixture",
                source_type="web",
                authority_score=0.8,
                authority_reason="fixture",
                metadata={
                    "source_role": "first_party",
                    "source_region": "CN",
                    "official_entry_evidence_type": "official_regional_link",
                    "official_entry_discovery_url": "https://www.akindo-sushiro.co.jp/cn/",
                    "official_entry_target_url": "https://mp.weixin.qq.com/s/sushiro-guangzhou",
                    "official_entry_target_label": "广州",
                    "official_entry_region": "CN",
                    "official_entry_verification": "requires_manual_confirmation",
                    "auto_ingestible": False,
                },
            )
        ]


class RecordingIngestion:
    def __init__(self) -> None:
        self.source_ids: list[int] = []

    def ingest_source(self, source_id: int) -> None:
        self.source_ids.append(source_id)


class NoopBuild:
    def run(self, project_id: int) -> None:
        raise AssertionError("An entry-only result must not build automatically.")


def test_mainland_scope_does_not_accept_taiwan_official_page_as_direct_authority():
    taiwan = _draft(
        "taiwan",
        "https://www.sushiro.com.tw/",
        title="首頁 - 台湾スシロー 台灣壽司郎",
    )

    plan = build_selection_plan("寿司郎在线取号流程", [taiwan], language="zh")

    assert plan.queue == []
    assert plan.terminal_reason == "cross_region_official_only"
    assert plan.assessed[0].metadata["source_role"] == "first_party"
    assert plan.assessed[0].metadata["source_region"] == "TW"
    assert plan.assessed[0].metadata["region_match"] == "cross_region"


def test_brand_named_third_party_h5_cannot_pass_official_first_gate():
    h5 = _draft(
        "helper",
        "https://sushiro.chinatsu1124.com/",
        title="寿司郎取号小助手",
    )

    plan = build_selection_plan("寿司郎在线取号流程", [h5], language="zh")

    assert plan.queue == []
    assert plan.terminal_reason == "evidence_insufficient"
    assert plan.assessed[0].metadata["source_role"] == "independent_coverage"


def test_mainland_news_mention_does_not_become_brand_domain_evidence():
    taiwan = _draft(
        "taiwan",
        "https://www.sushiro.com.tw/",
        title="首頁 - 台湾スシロー 台灣壽司郎",
    )
    news = _draft(
        "news",
        "https://news.example.com/sushiro",
        title="寿司郎中国大陆门店排队新规",
    )

    plan = build_selection_plan("寿司郎在线取号流程", [taiwan, news], language="zh")

    roles = {candidate.provider_source_id: candidate.metadata["source_role"] for candidate in plan.assessed}
    assert roles["taiwan"] == "first_party"
    assert roles["news"] == "independent_coverage"


def test_brand_domain_alias_can_link_regional_site_to_operator_homepage():
    taiwan = _draft(
        "taiwan",
        "https://www.sushiro.com.tw/",
        title="首頁 - 台湾スシロー 台灣壽司郎",
    )
    operator = _draft(
        "operator",
        "https://www.akindo-sushiro.co.jp/cn/",
        title="寿司郎",
    )

    plan = build_selection_plan("寿司郎在线取号流程", [taiwan, operator], language="zh")

    roles = {candidate.provider_source_id: candidate.metadata["source_role"] for candidate in plan.assessed}
    assert roles["operator"] == "first_party"
    assert plan.assessed[1].metadata["is_direct_authority"] is True


def test_official_page_link_to_wechat_is_retained_but_not_auto_ingestible():
    discovery = _draft(
        "sushiro-cn",
        "https://www.akindo-sushiro.co.jp/cn/",
        title="SUSHIRO - No.1 SUSHI sales in Japan",
        metadata={"brand_domain_candidate": True, "region_match": "unknown"},
    )
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    '<a href="https://mp.weixin.qq.com/s/guangzhou-sushiro">广州</a>'
                    '<a href="https://beian.miit.gov.cn/">粤ICP备</a>'
                ),
            )
        )
    )

    entries = HttpOfficialEntryInspector(client=client).inspect(
        target_region="CN", candidates=[discovery]
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.metadata["official_entry_discovery_url"] == discovery.url
    assert entry.metadata["official_entry_target_url"] == entry.url
    assert entry.metadata["official_entry_region"] == "CN"
    assert entry.metadata["auto_ingestible"] is False


def test_guided_workflow_records_regional_query_and_entry_only_recovery(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    scope = "寿司郎在线取号流程"
    project = DomainProjectRepository(database_path).create(
        CreateDomainProject(name="寿司郎取号", scope=scope, interaction_mode="guided", language="zh")
    )
    taiwan = _draft("taiwan", "https://www.sushiro.com.tw/", title="首頁 - 台湾スシロー 台灣壽司郎")
    h5 = _draft("helper", "https://sushiro.chinatsu1124.com/", title="寿司郎取号小助手")
    official_query = f"{scope} 官方 帮助 服务规则 公告"
    regional_query = regional_official_query(scope, language="zh")
    discovery = QueryDiscoveryProvider(
        {scope: [taiwan, h5], official_query: [], regional_query: []}
    )
    inspector = EntryOnlyInspector()
    ingestion = RecordingIngestion()

    try:
        AutopilotWorkflow(
            database_path=database_path,
            discovery_provider=discovery,
            ingestion_runner=ingestion,
            build_runner=NoopBuild(),
            official_entry_inspector=inspector,
        ).run(project.id)
    except ValueError as exc:
        assert "官方站点指向的本地区服务入口" in str(exc)
    else:
        raise AssertionError("Expected an entry-only result to require confirmation.")

    assert discovery.calls == [scope, official_query, regional_query]
    assert inspector.calls[0][0] == "CN"
    assert ingestion.source_ids == []
    assert SourceRepository(database_path).list_for_project(project.id) == []
    candidates = SourceCandidateRepository(database_path).list_for_project(project.id)
    entry = next(candidate for candidate in candidates if candidate.provider == "official_entry")
    assert entry.metadata["official_entry_target_label"] == "广州"
    selection = next(
        step
        for step in WorkflowRepository(database_path).list_for_project(project.id)[0].steps
        if step.step_name == "select_candidates" and step.status == "failed"
    )
    assert selection.output["terminal_reason"] == "official_entry_requires_confirmation"


def _draft(
    provider_source_id: str,
    url: str,
    *,
    title: str,
    source_type: str = "web",
    metadata: dict | None = None,
) -> SourceCandidateDraft:
    return SourceCandidateDraft(
        provider="fixture",
        provider_source_id=provider_source_id,
        title=title,
        url=url,
        snippet="fixture",
        source_type=source_type,
        authority_score=0.8,
        authority_reason="fixture",
        metadata=metadata or {},
    )
