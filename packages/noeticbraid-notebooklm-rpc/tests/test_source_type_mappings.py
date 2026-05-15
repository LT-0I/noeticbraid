from __future__ import annotations

from notebooklm import SourceType

from noeticbraid.tools.notebooklm_rpc import SOURCE_TYPE_TO_RECORD_TYPE, SOURCE_TYPE_TO_TAG


EXPECTED_SOURCE_TYPE_TO_TAG = {
    SourceType.GOOGLE_DOCS:          "noeticbraid/notebooklm/source/google-docs",
    SourceType.GOOGLE_SLIDES:        "noeticbraid/notebooklm/source/google-slides",
    SourceType.GOOGLE_SPREADSHEET:   "noeticbraid/notebooklm/source/google-spreadsheet",
    SourceType.PDF:                  "noeticbraid/notebooklm/source/pdf",
    SourceType.PASTED_TEXT:          "noeticbraid/notebooklm/source/pasted-text",
    SourceType.WEB_PAGE:             "noeticbraid/notebooklm/source/web-page",
    SourceType.GOOGLE_DRIVE_AUDIO:   "noeticbraid/notebooklm/source/google-drive-audio",
    SourceType.GOOGLE_DRIVE_VIDEO:   "noeticbraid/notebooklm/source/google-drive-video",
    SourceType.YOUTUBE:              "noeticbraid/notebooklm/source/youtube",
    SourceType.MARKDOWN:             "noeticbraid/notebooklm/source/markdown",
    SourceType.DOCX:                 "noeticbraid/notebooklm/source/docx",
    SourceType.CSV:                  "noeticbraid/notebooklm/source/csv",
    SourceType.EPUB:                 "noeticbraid/notebooklm/source/epub",
    SourceType.IMAGE:                "noeticbraid/notebooklm/source/image",
    SourceType.MEDIA:                "noeticbraid/notebooklm/source/media",
    SourceType.UNKNOWN:              "noeticbraid/notebooklm/source/unknown",
}


EXPECTED_SOURCE_TYPE_TO_RECORD_TYPE = {
    SourceType.GOOGLE_DOCS:          "user_note",
    SourceType.GOOGLE_SLIDES:        "user_note",
    SourceType.GOOGLE_SPREADSHEET:   "user_note",
    SourceType.PDF:                  "paper",
    SourceType.PASTED_TEXT:          "user_note",
    SourceType.WEB_PAGE:             "web_page",
    SourceType.GOOGLE_DRIVE_AUDIO:   "user_note",
    SourceType.GOOGLE_DRIVE_VIDEO:   "user_note",
    SourceType.YOUTUBE:              "web_page",
    SourceType.MARKDOWN:             "user_note",
    SourceType.DOCX:                 "user_note",
    SourceType.CSV:                  "user_note",
    SourceType.EPUB:                 "paper",
    SourceType.IMAGE:                "user_note",
    SourceType.MEDIA:                "user_note",
    SourceType.UNKNOWN:              "user_note",
}


def test_source_type_to_tag_covers_all_16_members():
    assert set(SOURCE_TYPE_TO_TAG.keys()) == set(SourceType)
    assert len(SOURCE_TYPE_TO_TAG) == 16


def test_source_type_to_tag_dict_byte_equal():
    assert SOURCE_TYPE_TO_TAG == EXPECTED_SOURCE_TYPE_TO_TAG


def test_source_type_to_record_type_covers_all_16_members():
    assert set(SOURCE_TYPE_TO_RECORD_TYPE.keys()) == set(SourceType)
    assert len(SOURCE_TYPE_TO_RECORD_TYPE) == 16


def test_source_type_to_record_type_values_in_schema_enum():
    assert set(SOURCE_TYPE_TO_RECORD_TYPE.values()) <= {
        "user_note",
        "web_page",
        "github_repo",
        "paper",
        "ai_output",
    }


def test_source_type_to_record_type_dict_byte_equal():
    assert SOURCE_TYPE_TO_RECORD_TYPE == EXPECTED_SOURCE_TYPE_TO_RECORD_TYPE


def test_all_tags_match_noeticbraid_prefix():
    assert all(tag.startswith("noeticbraid/notebooklm/source/") for tag in SOURCE_TYPE_TO_TAG.values())
