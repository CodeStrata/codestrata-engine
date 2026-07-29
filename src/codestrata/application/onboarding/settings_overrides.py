"""Settings overrides for repository onboarding (Phase 5.11)."""

from __future__ import annotations

from codestrata.config.settings import CodestrataSettings


def apply_onboarding_settings(
    settings: CodestrataSettings,
    *,
    skip_index: bool,
    provider: str | None,
    enable_roadmap: bool = True,
) -> CodestrataSettings:
    """Return settings with knowledge (and optionally roadmap) enabled for onboard.

    Does not mutate the caller's settings object.
    """

    knowledge = settings.knowledge.model_copy(deep=True)
    report = settings.report.model_copy(deep=True)
    ai = settings.ai.model_copy(deep=True)

    knowledge = knowledge.model_copy(update={"enabled": True})
    if skip_index:
        knowledge = knowledge.model_copy(
            update={
                "projection": knowledge.projection.model_copy(update={"enabled": False}),
                "chunking": knowledge.chunking.model_copy(update={"enabled": False}),
                "embedding": knowledge.embedding.model_copy(update={"enabled": False}),
                "indexing": knowledge.indexing.model_copy(update={"enabled": False}),
            }
        )
    else:
        knowledge = knowledge.model_copy(
            update={
                "projection": knowledge.projection.model_copy(update={"enabled": True}),
                "chunking": knowledge.chunking.model_copy(update={"enabled": True}),
                "embedding": knowledge.embedding.model_copy(update={"enabled": True}),
                "indexing": knowledge.indexing.model_copy(update={"enabled": True}),
            }
        )

    if provider is not None:
        name = provider.strip().lower()
        ai = ai.model_copy(update={"embedding_provider": name})
        knowledge = knowledge.model_copy(
            update={
                "embedding": knowledge.embedding.model_copy(update={"provider": name}),
            }
        )
    elif not skip_index:
        # Keep knowledge.embedding.provider aligned with [ai].embedding_provider.
        knowledge = knowledge.model_copy(
            update={
                "embedding": knowledge.embedding.model_copy(
                    update={"provider": ai.embedding_provider}
                ),
            }
        )

    if enable_roadmap:
        report = report.model_copy(
            update={
                "sections": report.sections.model_copy(
                    update={
                        "roadmap": report.sections.roadmap.model_copy(
                            update={"enabled": True}
                        )
                    }
                )
            }
        )

    return settings.model_copy(
        update={
            "knowledge": knowledge,
            "report": report,
            "ai": ai,
        }
    )
