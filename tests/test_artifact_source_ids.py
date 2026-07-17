from __future__ import annotations

from domain_atlas.core.db import connect, initialize_database
from domain_atlas.domain.artifacts import KnowledgeArtifactRepository
from domain_atlas.domain.projects import CreateDomainProject, DomainProjectRepository
from domain_atlas.domain.sources import CreateSource, SourceRepository


def test_artifact_repository_accepts_citation_style_source_ids(tmp_path):
    database_path = tmp_path / "domain_atlas.sqlite3"
    initialize_database(database_path)
    project = DomainProjectRepository(database_path).create(CreateDomainProject(name="Dataphin"))
    source = SourceRepository(database_path).create(
        CreateSource(
            project_id=project.id,
            source_type="markdown",
            title="Dataphin source",
            locator="fixture:dataphin",
        )
    )

    KnowledgeArtifactRepository(database_path).replace_project_artifacts(
        project.id,
        {
            "source_profiles": [
                {
                    "source_id": f"S{source.id}-C1",
                    "summary": "资料摘要。",
                    "citations": [f"S{source.id}-C1"],
                },
                {"source_id": "not-a-source", "summary": "应被忽略。"},
            ]
        },
    )

    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT source_id, summary FROM source_profiles WHERE project_id = ?",
            (project.id,),
        ).fetchall()
    assert [(row["source_id"], row["summary"]) for row in rows] == [(source.id, "资料摘要。")]
