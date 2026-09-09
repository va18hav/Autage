from services.db.models.runbooks import (
    Runbook,
    Runbooks,
    RunbookSection,
    RunbookSections,
)


def test_runbook_and_section_models_and_aliases():
    assert Runbook is Runbooks
    assert RunbookSection is RunbookSections
    assert Runbook.__tablename__ == "runbooks"
    assert RunbookSection.__tablename__ == "runbook_sections"

    rb = Runbook(
        title="Redis Failover",
        description="Sentinel failover runbook",
        service="redis",
        triggers=["RedisDown"],
        raw_content="# Redis Failover\n## Promote Replica",
    )
    sec = RunbookSection(
        order_index=0,
        heading="Promote Replica",
        content="redis-cli failover",
    )
    rb.sections.append(sec)
    assert rb.sections[0].heading == "Promote Replica"
    assert sec.runbook is rb
