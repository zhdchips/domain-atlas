from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.source_candidates import SourceCandidateDraft, SourceCandidateRepository
from domain_atlas.domain.sources import SourceRepository
from domain_atlas.domain.workflow import WorkflowRepository
from domain_atlas.web.app import create_app
from domain_atlas.workflow.autopilot import AutopilotWorkflow
from domain_atlas.workflow.source_policy import regional_official_query


@pytest.mark.e2e
def test_guided_mainland_entry_only_flow_preserves_provenance_without_ingestion(tmp_path):
    settings = Settings(data_dir=tmp_path)
    scope = "寿司郎在线取号流程"
    regional_query = regional_official_query(scope, language="zh")
    autopilot = AutopilotWorkflow(
        database_path=settings.database_path,
        discovery_provider=RecordedDiscovery(
            {
                scope: [
                    _candidate("taiwan", "https://www.sushiro.com.tw/", "首頁 - 台湾スシロー 台灣壽司郎"),
                    _candidate("operator", "https://www.akindo-sushiro.co.jp/cn/", "寿司郎"),
                ],
                f"{scope} 官方 帮助 服务规则 公告": [],
                regional_query: [],
            }
        ),
        ingestion_runner=RecordingIngestion(),
        build_runner=NoBuild(),
        official_entry_inspector=RecordedEntryInspector(),
    )
    app = create_app(settings, autopilot_runner=autopilot)
    project = DomainProjectRepository(settings.database_path).create(
        CreateDomainProject(name="寿司郎取号", scope=scope, interaction_mode="guided")
    )

    response = TestClient(app).post(f"/domains/{project.id}/autopilot", follow_redirects=False)

    assert response.status_code == 303
    _wait_for_workflow(settings.database_path, project.id)
    run = WorkflowRepository(settings.database_path).list_for_project(project.id)[0]
    selection = next(
        step
        for step in run.steps
        if step.step_name == "select_candidates" and step.status == "failed"
    )
    assert run.status == "failed"
    assert selection.output["terminal_reason"] == "official_entry_requires_confirmation"
    assert SourceRepository(settings.database_path).list_for_project(project.id) == []
    entry = next(
        candidate
        for candidate in SourceCandidateRepository(settings.database_path).list_for_project(project.id)
        if candidate.provider == "official_entry"
    )
    assert entry.metadata["official_entry_discovery_url"] == "https://www.akindo-sushiro.co.jp/cn/"
    assert entry.metadata["official_entry_target_url"] == entry.url


class RecordedDiscovery:
    def __init__(self, responses: dict[str, list[SourceCandidateDraft]]) -> None:
        self.responses = responses

    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        return self.responses.get(query, [])


class RecordedEntryInspector:
    def inspect(self, *, target_region: str, candidates: list[SourceCandidateDraft]):
        assert target_region == "CN"
        return [
            SourceCandidateDraft(
                provider="official_entry",
                provider_source_id="sushiro-guangzhou",
                title="广州寿司郎官方服务入口",
                url="https://mp.weixin.qq.com/s/sushiro-guangzhou",
                snippet="由官方简体中文站链接发现。",
                source_type="web",
                authority_score=0.8,
                authority_reason="品牌官方站点的地区入口链接",
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
    def ingest_source(self, source_id: int) -> None:
        raise AssertionError("entry-only result must not auto-ingest")


class NoBuild:
    def run(self, project_id: int) -> None:
        raise AssertionError("entry-only result must not build")


def _candidate(identifier: str, url: str, title: str) -> SourceCandidateDraft:
    return SourceCandidateDraft(
        provider="fixture",
        provider_source_id=identifier,
        title=title,
        url=url,
        snippet="fixture",
        source_type="web",
        authority_score=0.8,
        authority_reason="fixture",
    )


def _wait_for_workflow(database_path, project_id: int) -> None:
    repository = WorkflowRepository(database_path)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        runs = repository.list_for_project(project_id)
        if runs and not any(run.status in {"queued", "running"} for run in runs):
            return
        time.sleep(0.02)
    raise AssertionError("guided regional-entry workflow did not finish")
