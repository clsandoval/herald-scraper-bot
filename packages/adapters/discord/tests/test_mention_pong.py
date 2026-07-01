"""Mention-gate unit test for HeraldBot (DISC-01 at the code level).

No live Discord connection -- `discord.Message`/`discord.Client` internals
are mocked. Verifies the three `on_message` behaviors: pong iff mentioned,
never on un-mentioned messages, never on self-authored messages.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_bot() -> object:
    """Build a HeraldBot with `discord.Client.__init__` bypassed.

    `discord.Client.__init__` opens a real aiohttp connector/loop wiring we
    don't want in a unit test -- construct via `__new__` and set the
    attributes `on_message` actually touches. `discord.Client.user` is a
    read-only property backed by `self._connection.user`, so it's faked via
    the connection state rather than a direct attribute set.
    """
    from daimon.adapters.discord.bot import HeraldBot

    bot = HeraldBot.__new__(HeraldBot)
    bot._connection = MagicMock(user=MagicMock(name="bot_user"))
    bot.runtime = MagicMock(name="runtime")
    return bot


def _make_message(*, author, mentions):
    message = MagicMock()
    message.author = author
    message.mentions = mentions
    message.channel.send = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_pong_sent_when_mentioned() -> None:
    bot = _make_bot()
    message = _make_message(author=MagicMock(name="someone_else"), mentions=[bot.user])

    await bot.on_message(message)

    message.channel.send.assert_awaited_once_with("pong")


@pytest.mark.asyncio
async def test_no_pong_when_not_mentioned() -> None:
    bot = _make_bot()
    message = _make_message(author=MagicMock(name="someone_else"), mentions=[])

    await bot.on_message(message)

    message.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_pong_for_self_authored_message() -> None:
    bot = _make_bot()
    # Author is the bot itself -- even if (implausibly) self-mentioned, the
    # self-check must short-circuit before the mention check.
    message = _make_message(author=bot.user, mentions=[bot.user])

    await bot.on_message(message)

    message.channel.send.assert_not_awaited()
