from __future__ import annotations

from fastapi.testclient import TestClient

from domain_atlas.core.settings import Settings
from domain_atlas.domain.source_candidates import SourceCandidateDraft
from domain_atlas.providers.vector_index import RetrievedChunk
from domain_atlas.web.app import create_app


class FakeDiscoveryProvider:
    def search(self, query: str, limit: int) -> list[SourceCandidateDraft]:
        assert query
        assert limit == 12
        return [
            SourceCandidateDraft(
                provider="exa",
                provider_source_id="src-1",
                title="Agent Docs",
                url="https://docs.example.com/agents",
                snippet="Official docs for agents.",
                source_type="official_docs",
                publisher="Example Docs",
                published_at="2026-01-01",
                authority_score=0.9,
                authority_reason="官方资料",
            )
        ]


class FakeEmbeddingProvider:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(len(text))] for text in texts]


class FakeVectorIndex:
    def __init__(self):
        self.calls = []

    def upsert_chunks(self, *, project_id: int, chunks, embeddings) -> None:
        self.calls.append((project_id, len(chunks), len(embeddings)))

    def upsert_wiki_sections(self, *, project_id: int, sections, embeddings) -> None:
        self.calls.append(("wiki", project_id, len(sections), len(embeddings)))

    def query(self, *, project_id: int, query_embedding: list[float], limit: int):
        return [
            RetrievedChunk(
                chunk_uid="chunk:1",
                text="Agents use tools.",
                citation_label="S1-C1",
                source_id=1,
                distance=0.1,
                metadata={},
            )
        ]


class FakeChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "source_profiles": [
                {
                    "source_id": 1,
                    "summary": "资料介绍 Agent。",
                    "authority_note": "测试资料。",
                    "coverage_note": "基础覆盖。",
                    "citations": ["S1-C1"],
                }
            ],
            "concepts": [
                {
                    "name": "Agent",
                    "definition": "Agent 使用工具完成任务。",
                    "prerequisites": [],
                    "related": ["Tool Use"],
                    "citations": ["S1-C1"],
                }
            ],
            "concept_edges": [
                {
                    "source": "Agent",
                    "target": "Tool Use",
                    "relation": "related",
                    "citations": ["S1-C1"],
                }
            ],
            "wiki_pages": [
                {
                    "title": "Agent",
                    "topic_path": "核心概念/Agent",
                    "summary": "Agent 使用工具完成任务。",
                    "body_markdown": "## Agent\nAgent 使用工具完成任务。[S1-C1]",
                    "citations": ["S1-C1"],
                }
            ],
            "learning_modules": [
                {
                    "stage": stage,
                    "title": title,
                    "objectives": ["建立理解"],
                    "readings": ["Agent [S1-C1]"],
                    "key_concepts": ["Agent"],
                    "check_questions": ["什么是 Agent？"],
                    "practice_task": "解释 Agent。",
                    "citations": ["S1-C1"],
                }
                for stage, title in enumerate(
                    ["入门认知", "核心概念", "关键方法", "实践应用", "进阶专题"],
                    start=1,
                )
            ],
        }


class FakeQAChatProvider:
    def complete_json(self, *, system_prompt: str, user_prompt: str):
        return {
            "answer": "Agent 会使用工具完成任务。",
            "citations": ["S1-C1"],
            "evidence_status": "sufficient",
        }


def test_health_route_returns_ok(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "Domain Atlas"}


def test_home_route_renders_skeleton(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Domain Atlas" in response.text
    assert "创建领域项目" in response.text


def test_create_domain_redirects_to_dashboard(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/domains",
        data={
            "name": "LLM Agents",
            "goal": "建立系统化知识地图",
            "level": "beginner",
            "language": "zh",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert dashboard.status_code == 200
    assert "LLM Agents" in dashboard.text
    assert "建立系统化知识地图" in dashboard.text
    assert "学习路线" in dashboard.text


def test_home_lists_existing_projects(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    client.post("/domains", data={"name": "合成生物学"})

    response = client.get("/")

    assert response.status_code == 200
    assert "合成生物学" in response.text
    assert "/domains/1" in response.text


def test_missing_domain_returns_404(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/domains/404")

    assert response.status_code == 404


def test_discover_sources_lists_candidates_and_confirm_accepts(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), discovery_provider=FakeDiscoveryProvider())
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    discover = client.post(
        "/domains/1/discover",
        data={"query": ""},
        follow_redirects=False,
    )

    assert discover.status_code == 303
    assert discover.headers["location"] == "/domains/1"

    dashboard = client.get("/domains/1")
    assert "Agent Docs" in dashboard.text
    assert "Official docs for agents." in dashboard.text
    assert "官方资料" in dashboard.text

    confirm = client.post(
        "/domains/1/candidates/1/confirm",
        follow_redirects=False,
    )

    assert confirm.status_code == 303
    accepted_dashboard = client.get("/domains/1")
    assert "已确认" in accepted_dashboard.text
    assert "Agent Docs" in accepted_dashboard.text
    assert "pending" in accepted_dashboard.text


def test_add_url_source_route_lists_pending_source(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    response = client.post(
        "/domains/1/sources/url",
        data={"url": "https://docs.example.com/agents", "title": "Agent Docs"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    dashboard = client.get("/domains/1")
    assert "Agent Docs" in dashboard.text
    assert "https://docs.example.com/agents" in dashboard.text
    assert "pending" in dashboard.text


def test_upload_markdown_and_ingest_from_dashboard(tmp_path):
    vector_index = FakeVectorIndex()
    app = create_app(
        Settings(data_dir=tmp_path),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    upload = client.post(
        "/domains/1/sources/file",
        files={"file": ("agents.md", b"# Agents\n\nAgents use tools.", "text/markdown")},
        follow_redirects=False,
    )

    assert upload.status_code == 303
    before = client.get("/domains/1")
    assert "agents" in before.text
    assert "pending" in before.text

    ingest = client.post("/domains/1/sources/1/ingest", follow_redirects=False)

    assert ingest.status_code == 303
    after = client.get("/domains/1")
    assert "已摄取" in after.text
    assert "Chunks" in after.text
    assert vector_index.calls == [(1, 1, 1)]


def test_build_knowledge_route_renders_wiki_and_learning_path(tmp_path):
    vector_index = FakeVectorIndex()
    app = create_app(
        Settings(data_dir=tmp_path),
        chat_provider=FakeChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=vector_index,
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})
    client.post(
        "/domains/1/sources/file",
        files={"file": ("agents.md", b"# Agents\n\nAgents use tools.", "text/markdown")},
    )
    client.post("/domains/1/sources/1/ingest")

    build = client.post("/domains/1/build", follow_redirects=False)

    assert build.status_code == 303
    dashboard = client.get("/domains/1")
    assert "completed" in dashboard.text
    wiki = client.get("/domains/1/wiki")
    assert "Agent 使用工具完成任务" in wiki.text
    path = client.get("/domains/1/path")
    assert "入门认知" in path.text
    assert "进阶专题" in path.text
    assert ("wiki", 1, 1, 1) in vector_index.calls


def test_qa_route_records_cited_answer(tmp_path):
    app = create_app(
        Settings(data_dir=tmp_path),
        chat_provider=FakeQAChatProvider(),
        embedding_provider=FakeEmbeddingProvider(),
        vector_index=FakeVectorIndex(),
    )
    client = TestClient(app)
    client.post("/domains", data={"name": "LLM Agents"})

    response = client.post(
        "/domains/1/qa",
        data={"question": "Agent 是什么？"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    qa_page = client.get("/domains/1/qa")
    assert "Agent 会使用工具完成任务" in qa_page.text
    assert "S1-C1" in qa_page.text
