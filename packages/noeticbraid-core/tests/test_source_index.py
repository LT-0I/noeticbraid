"""SourceIndex pytest (Stage 2 GPT-B)."""

from __future__ import annotations

import types
from datetime import datetime, timezone
from pathlib import Path

from noeticbraid_core.schemas import SourceRecord
from noeticbraid_core.source_index import FileBucketSourceIndex, SourceIndexBackend


def make_source(
    source_ref_id: str = "source_001",
    content_hash: str = "sha256:" + "a" * 64,
    canonical_url: str | None = "https://example.com/a",
    title: str = "Example",
) -> SourceRecord:
    return SourceRecord(
        source_ref_id=source_ref_id,
        source_type="web_page",
        title=title,
        canonical_url=canonical_url,
        captured_at=datetime.now(timezone.utc),
        retrieved_by_run_id="run_001",
        content_hash=content_hash,
        source_fingerprint=f"fingerprint_{source_ref_id}",
        evidence_role="user_context",
        used_for_purpose="other",
    )


class TestSourceIndexPutGet:
    def test_put_get_roundtrip(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec = make_source()

        idx.put(rec)
        loaded = idx.get(rec.content_hash)

        assert loaded is not None
        assert loaded.source_ref_id == "source_001"
        assert loaded.canonical_url == "https://example.com/a"

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        missing = "sha256:" + "f" * 64
        assert idx.get(missing) is None

    def test_get_corrupted_returns_none(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec = make_source(content_hash="sha256:" + "c" * 64)
        idx.put(rec)
        path = idx.directory / "cc" / ("c" * 64 + ".json")
        path.write_text("not-json", encoding="utf-8")

        assert idx.get(rec.content_hash) is None


class TestSourceIndexWindowsPathSafe:
    def test_no_colon_in_file_path(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec = make_source()
        idx.put(rec)

        for entry in idx.directory.rglob("*"):
            assert ":" not in entry.name, f"colon in {entry}"

    def test_bucket_path_layout(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec = make_source(content_hash="sha256:" + "ab" + "c" * 62)
        idx.put(rec)
        expected = tmp_path / "state" / "source_index" / "ab" / ("ab" + "c" * 62 + ".json")

        assert expected.exists()


class TestSourceIndexFindByUrl:
    def test_find_by_url_returns_match(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec_a = make_source(
            source_ref_id="source_a",
            content_hash="sha256:" + "a" * 64,
            canonical_url="https://example.com/a",
        )
        rec_b = make_source(
            source_ref_id="source_b",
            content_hash="sha256:" + "b" * 64,
            canonical_url="https://example.com/b",
        )
        idx.put(rec_a)
        idx.put(rec_b)

        results = list(idx.find_by_url("https://example.com/a"))

        assert len(results) == 1
        assert results[0].source_ref_id == "source_a"

    def test_find_by_url_lazy_iter(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        for i in range(3):
            idx.put(
                make_source(
                    source_ref_id=f"source_{i:03d}",
                    content_hash=f"sha256:{i:064x}",
                    canonical_url="https://example.com/same",
                )
            )

        gen = idx.find_by_url("https://example.com/same")
        first = next(gen)

        assert isinstance(gen, types.GeneratorType) or hasattr(gen, "__next__")
        assert first.canonical_url == "https://example.com/same"

    def test_find_by_url_empty(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        assert list(idx.find_by_url("https://example.com/missing")) == []

    def test_find_by_url_skips_corrupted_records(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        good = make_source(
            source_ref_id="source_good",
            content_hash="sha256:" + "d" * 64,
            canonical_url="https://example.com/good",
        )
        bad = make_source(
            source_ref_id="source_bad",
            content_hash="sha256:" + "e" * 64,
            canonical_url="https://example.com/good",
        )
        idx.put(good)
        idx.put(bad)
        (idx.directory / "ee" / ("e" * 64 + ".json")).write_text("{bad json", encoding="utf-8")

        results = list(idx.find_by_url("https://example.com/good"))

        assert [record.source_ref_id for record in results] == ["source_good"]

    def test_find_by_url_ignores_none_canonical_url(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        rec = make_source(
            source_ref_id="source_none",
            content_hash="sha256:" + "9" * 64,
            canonical_url=None,
        )
        idx.put(rec)

        assert list(idx.find_by_url("https://example.com/a")) == []


class TestSourceIndexProtocol:
    def test_filebucket_isinstance_protocol(self, tmp_path: Path) -> None:
        idx = FileBucketSourceIndex(root=tmp_path)
        assert isinstance(idx, SourceIndexBackend)
