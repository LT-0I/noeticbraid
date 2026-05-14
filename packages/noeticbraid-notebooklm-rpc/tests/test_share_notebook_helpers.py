from __future__ import annotations

import notebooklm
import pytest
from notebooklm import SharePermission, ShareViewLevel

from noeticbraid.tools.notebooklm_rpc import (
    NotebookLMLifecycleError,
    set_notebook_public_with_view_level,
    share_notebook_with_user,
)


class FakeSharing:
    def __init__(self, *, add_error=None, set_public_error=None, set_view_level_error=None):
        self.calls = []
        self.add_error = add_error
        self.set_public_error = set_public_error
        self.set_view_level_error = set_view_level_error
        self.add_status = object()
        self.public_status = object()
        self.view_level_status = object()

    async def add_user(self, notebook_id, email, *, permission, notify, welcome_message):
        self.calls.append(("add_user", notebook_id, email, permission, notify, welcome_message))
        if self.add_error is not None:
            raise self.add_error
        return self.add_status

    async def set_public(self, notebook_id, public):
        self.calls.append(("set_public", notebook_id, public))
        if self.set_public_error is not None:
            raise self.set_public_error
        return self.public_status

    async def set_view_level(self, notebook_id, view_level):
        self.calls.append(("set_view_level", notebook_id, view_level))
        if self.set_view_level_error is not None:
            raise self.set_view_level_error
        return self.view_level_status


class FakeClient:
    def __init__(self, sharing=None):
        self.sharing = sharing or FakeSharing()


def assert_error_class(excinfo, error_class: str):
    assert excinfo.value.error_class == error_class
    assert str(excinfo.value).startswith(f"{error_class}: ")


class TestShareNotebookWithUser:
    async def test_add_user_only_no_view_level(self):
        client = FakeClient()

        status = await share_notebook_with_user(client, "nb_1", "user@example.com", view_level=None)

        assert status is client.sharing.add_status
        assert client.sharing.calls == [
            ("add_user", "nb_1", "user@example.com", SharePermission.VIEWER, True, "")
        ]

    async def test_add_user_then_set_view_level(self):
        client = FakeClient()

        status = await share_notebook_with_user(
            client,
            "nb_1",
            "user@example.com",
            view_level=ShareViewLevel.CHAT_ONLY,
        )

        assert status is client.sharing.view_level_status
        assert [call[0] for call in client.sharing.calls] == ["add_user", "set_view_level"]
        assert client.sharing.calls[1] == ("set_view_level", "nb_1", ShareViewLevel.CHAT_ONLY)

    @pytest.mark.parametrize(
        "email",
        ["a@b.c", "user@example.com", "user+tag@sub.example.co.uk", "e@dom.io"],
    )
    async def test_email_regex_valid_inputs_pass(self, email):
        client = FakeClient()

        await share_notebook_with_user(client, "nb_1", email)

        assert client.sharing.calls[0][0] == "add_user"
        assert client.sharing.calls[0][2] == email

    @pytest.mark.parametrize("email", ["not-email", "@example.com", "user@", "user@host"])
    async def test_email_regex_invalid_inputs_raise(self, email):
        client = FakeClient()

        with pytest.raises(NotebookLMLifecycleError) as excinfo:
            await share_notebook_with_user(client, "nb_1", email)

        assert_error_class(excinfo, "invalid_email")
        assert client.sharing.calls == []

    async def test_empty_notebook_id_raises(self):
        client = FakeClient()

        with pytest.raises(NotebookLMLifecycleError) as excinfo:
            await share_notebook_with_user(client, "", "user@example.com")

        assert_error_class(excinfo, "empty_notebook_id")
        assert client.sharing.calls == []

    async def test_passes_permission_and_notify(self):
        client = FakeClient()

        await share_notebook_with_user(
            client,
            "nb_1",
            "user@example.com",
            permission=SharePermission.EDITOR,
            notify=False,
            welcome_message="hi",
        )

        assert client.sharing.calls == [
            ("add_user", "nb_1", "user@example.com", SharePermission.EDITOR, False, "hi")
        ]

    async def test_upstream_error_propagates(self):
        error = notebooklm.NotebookLMError("upstream blew up")
        client = FakeClient(FakeSharing(add_error=error))

        with pytest.raises(notebooklm.NotebookLMError) as excinfo:
            await share_notebook_with_user(client, "nb_1", "user@example.com")

        assert excinfo.value is error


class TestSetNotebookPublicWithViewLevel:
    async def test_set_public_then_view_level_order(self):
        client = FakeClient()

        status = await set_notebook_public_with_view_level(
            client,
            "nb_1",
            public=True,
            view_level=ShareViewLevel.CHAT_ONLY,
        )

        assert status is client.sharing.view_level_status
        assert [call[0] for call in client.sharing.calls] == ["set_public", "set_view_level"]
        assert client.sharing.calls[0] == ("set_public", "nb_1", True)
        assert client.sharing.calls[1] == ("set_view_level", "nb_1", ShareViewLevel.CHAT_ONLY)

    async def test_set_view_level_always_runs_even_when_default(self):
        client = FakeClient()

        await set_notebook_public_with_view_level(client, "nb_1", public=True)

        assert [call[0] for call in client.sharing.calls].count("set_view_level") == 1
        assert client.sharing.calls[1] == ("set_view_level", "nb_1", ShareViewLevel.FULL_NOTEBOOK)

    async def test_empty_notebook_id_raises(self):
        client = FakeClient()

        with pytest.raises(NotebookLMLifecycleError) as excinfo:
            await set_notebook_public_with_view_level(client, "", public=True)

        assert_error_class(excinfo, "empty_notebook_id")
        assert client.sharing.calls == []

    async def test_passes_public_true_and_view_level(self):
        client = FakeClient()

        await set_notebook_public_with_view_level(
            client,
            "nb_1",
            public=True,
            view_level=ShareViewLevel.CHAT_ONLY,
        )

        assert client.sharing.calls[0] == ("set_public", "nb_1", True)
        assert client.sharing.calls[1] == ("set_view_level", "nb_1", ShareViewLevel.CHAT_ONLY)

    async def test_passes_public_false_and_view_level(self):
        client = FakeClient()

        await set_notebook_public_with_view_level(
            client,
            "nb_1",
            public=False,
            view_level=ShareViewLevel.FULL_NOTEBOOK,
        )

        assert client.sharing.calls[0] == ("set_public", "nb_1", False)
        assert client.sharing.calls[1] == ("set_view_level", "nb_1", ShareViewLevel.FULL_NOTEBOOK)

    async def test_upstream_error_in_set_public_propagates(self):
        error = notebooklm.NotebookLMError("upstream blew up")
        client = FakeClient(FakeSharing(set_public_error=error))

        with pytest.raises(notebooklm.NotebookLMError) as excinfo:
            await set_notebook_public_with_view_level(client, "nb_1", public=True)

        assert excinfo.value is error
        assert [call[0] for call in client.sharing.calls] == ["set_public"]

    async def test_upstream_error_in_set_view_level_propagates(self):
        error = notebooklm.NotebookLMError("upstream blew up")
        client = FakeClient(FakeSharing(set_view_level_error=error))

        with pytest.raises(notebooklm.NotebookLMError) as excinfo:
            await set_notebook_public_with_view_level(client, "nb_1", public=True)

        assert excinfo.value is error
        assert [call[0] for call in client.sharing.calls] == ["set_public", "set_view_level"]
