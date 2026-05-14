from __future__ import annotations

import notebooklm

from noeticbraid.tools.notebooklm_rpc import (
    ARTIFACT_KIND_TO_TAG,
    KIND_TO_DOWNLOAD_METHOD,
    ArtifactKind,
)


SPEC_TAGS = {
    ArtifactKind.AUDIO: "noeticbraid/notebooklm/audio",
    ArtifactKind.VIDEO: "noeticbraid/notebooklm/video",
    ArtifactKind.CINEMATIC_VIDEO: "noeticbraid/notebooklm/cinematic-video",
    ArtifactKind.REPORT: "noeticbraid/notebooklm/report",
    ArtifactKind.STUDY_GUIDE: "noeticbraid/notebooklm/study-guide",
    ArtifactKind.QUIZ: "noeticbraid/notebooklm/quiz",
    ArtifactKind.FLASHCARDS: "noeticbraid/notebooklm/flashcards",
    ArtifactKind.INFOGRAPHIC: "noeticbraid/notebooklm/infographic",
    ArtifactKind.SLIDE_DECK: "noeticbraid/notebooklm/slide-deck",
    ArtifactKind.DATA_TABLE: "noeticbraid/notebooklm/data-table",
    ArtifactKind.MIND_MAP: "noeticbraid/notebooklm/mind-map",
}

SPEC_DOWNLOAD_METHODS = {
    ArtifactKind.AUDIO: "download_audio",
    ArtifactKind.VIDEO: "download_video",
    ArtifactKind.CINEMATIC_VIDEO: "download_video",
    ArtifactKind.REPORT: "download_report",
    ArtifactKind.STUDY_GUIDE: "download_report",
    ArtifactKind.QUIZ: "download_quiz",
    ArtifactKind.FLASHCARDS: "download_flashcards",
    ArtifactKind.INFOGRAPHIC: "download_infographic",
    ArtifactKind.SLIDE_DECK: "download_slide_deck",
    ArtifactKind.DATA_TABLE: "download_data_table",
    ArtifactKind.MIND_MAP: "download_mind_map",
}


def test_artifact_kind_has_11_members():
    assert [kind.value for kind in ArtifactKind] == [
        "audio",
        "video",
        "cinematic_video",
        "report",
        "study_guide",
        "quiz",
        "flashcards",
        "infographic",
        "slide_deck",
        "data_table",
        "mind_map",
    ]
    assert len(list(ArtifactKind)) == 11


def test_artifact_kind_to_tag_covers_all_kinds():
    assert set(ARTIFACT_KIND_TO_TAG.keys()) == set(ArtifactKind)


def test_all_tags_match_noeticbraid_prefix():
    assert all(tag.startswith("noeticbraid/notebooklm/") for tag in ARTIFACT_KIND_TO_TAG.values())


def test_tag_mapping_byte_equal_to_spec():
    assert ARTIFACT_KIND_TO_TAG == SPEC_TAGS


def test_kind_to_download_method_covers_all_kinds():
    assert set(KIND_TO_DOWNLOAD_METHOD.keys()) == set(ArtifactKind)


def test_kind_to_download_method_byte_equal_to_spec():
    assert KIND_TO_DOWNLOAD_METHOD == SPEC_DOWNLOAD_METHODS


def test_all_download_method_names_exist_on_upstream():
    candidates = []
    client_module = getattr(notebooklm, "client", None)
    if client_module is not None:
        candidates.append(getattr(client_module, "ArtifactsAPI", None))
    artifacts_module = getattr(notebooklm, "_artifacts", None)
    if artifacts_module is not None:
        candidates.append(getattr(artifacts_module, "ArtifactsAPI", None))

    for method_name in set(KIND_TO_DOWNLOAD_METHOD.values()):
        assert any(callable(getattr(candidate, method_name, None)) for candidate in candidates)
