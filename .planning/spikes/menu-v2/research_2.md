# discord.py 2.7.1 Components V2 / LayoutView — spike findings

Verified by introspecting `/home/clsandoval/cs/herald-scraper-bot/.venv` (discord.py **2.7.1**, Python 3.14) and current docs (https://discordpy.readthedocs.io/en/stable/, https://github.com/Rapptz/discord.py). CV2 support landed in **2.6.0** (PR #10166); 2.7.1 fixed a LayoutView memory leak and view/cache binding.

## 1. Classes & constructor signatures (introspected, exact)
All in `discord.ui` unless noted:
- `LayoutView(*, timeout: Optional[float] = 180.0)` — subclass of `BaseView`, NOT of `View`. Methods: `add_item`, `remove_item`, `clear_items`, `find_item`, `walk_children`, `children`, `content_length()`, `total_children_count`, `has_components_v2()` (always True), `is_persistent()`, `from_message(message, *, timeout=180.0)`, `stop`, `wait`, `on_timeout`, `on_error`, `interaction_check`.
- `Container(*children: Item, accent_colour=None, accent_color=None, spoiler: bool = False, id: Optional[int] = None)` — top-level only; may contain ActionRow, TextDisplay, Section, MediaGallery, File, Separator. Subclassable (class-attr style like a View).
- `Section(*children: Union[Item, str], accessory: Item, id=None)` — children are TextDisplays (bare `str` auto-wrapped); `accessory` is keyword-REQUIRED (Thumbnail or Button).
- `TextDisplay(content: str, *, id=None)` — markdown supported (`# heading`, etc.).
- `Thumbnail(media: Union[str, discord.File, discord.UnfurledMediaItem], *, description=..., spoiler=..., id=None)` — docstring: media "can be a URL or a reference to an attachment that matches the `attachment://filename.extension` structure". Section accessory only.
- `MediaGallery(*items: MediaGalleryItem, id=None)`; `.add_item(*, media: Union[str, File, UnfurledMediaItem], description=..., spoiler=...) -> Self`. **`MediaGalleryItem` lives in `discord` (discord.components), NOT `discord.ui`**: `discord.MediaGalleryItem(media, *, description=..., spoiler=...)`.
- `File(media: Union[str, UnfurledMediaItem, SendableFile], *, spoiler=..., id=None)` — displays an uploaded file; media must be `attachment://name` for uploads.
- `Separator(*, visible: bool = True, spacing: SeparatorSpacing = SeparatorSpacing.small, id=None)` — `discord.SeparatorSpacing.small=1, .large=2`.
- `ActionRow(*children: Item, id=None)` — has `.button(...)` and `.select(...)` DECORATOR methods (see #3).
- `Label(*, text: str, component: Item, description=None, id=None)` — modal-only (wraps TextInput/Select in Modals), not for LayoutView messages.
- `discord.UnfurledMediaItem(url: str)`; `discord.File.uri` property returns `attachment://<filename>` (added 2.6).

## 2. Sending
- `await channel.send(view=my_layout_view)` — yes. Typed overloads allow ONLY: `file=`/`files=`, `delete_after`, `nonce`, `allowed_mentions`, `reference`, `mention_author`, `suppress_embeds`, `silent`. **`content=`, `embed(s)=`, `stickers=`, `tts` are NOT allowed with a LayoutView** (type-level; at runtime Discord's API 400s — the lib does not pre-validate this mix).
- The lib auto-sets message flag `IS_COMPONENTS_V2` (`MessageFlags.components_v2`, bit `1 << 15 = 32768`) in `discord/http.py handle_message_parameters` when `view.has_components_v2()`.
- `files=[discord.File('graph.png', filename='graph.png')]` + `Thumbnail('attachment://graph.png')` / `gallery.add_item(media='attachment://graph.png')` — supported and documented; or pass the `discord.File` object directly as `media` (Thumbnail extracts `.uri`). Serialized payload: `{"type": 11, "media": {"url": "attachment://graph.png"}, ...}` (verified via `view.to_components()`).
- Component type IDs in payload: ActionRow=1, Button=2, StringSelect=3, Section=9, TextDisplay=10, Thumbnail=11, MediaGallery=12, File=13, Separator=14, Container=17.
- Also works with `interaction.response.send_message(view=layout)` and `interaction.followup.send(view=layout)` (same content/embed restriction).

## 3. Callbacks, dynamic build, persistence
- Class-attr style: declare `row = ui.ActionRow()` inside a `Container` subclass (or directly on the LayoutView), then `@row.button(label=..., custom_id=..., style=..., emoji=..., disabled=..., id=...)` and `@row.select(cls=Select, options=..., placeholder=..., custom_id=..., min_values=..., max_values=...)`. Callback signature: `async def cb(self, interaction: discord.Interaction, item)`. URL/SKU buttons can't use the decorator — `ActionRow.add_item(Button(url=...))`.
- Dynamic: `btn = ui.Button(...); btn.callback = some_coro; row.add_item(btn); container.add_item(row); view.add_item(container)`. All `add_item`s return `Self` (chainable). Parent/view chain is correctly populated in 2.7.1 for both styles (verified: `btn.parent -> ActionRow`, `btn.view -> LayoutView`).
- `interaction_check`: `Item._run_checks` recurses up the parent chain (item → ActionRow → Container) AND the view-level `interaction_check` runs — so Container-level checks DO apply in 2.7.1 (this was broken in 2.6.4, see #6).
- Persistence: `LayoutView(timeout=None)` + explicit `custom_id` on every button/select, then `bot.add_view(view)` (`Client.add_view(view: BaseView, *, message_id=None)` accepts LayoutView). `LayoutView.from_message(msg)` exists for reconstruction. `ui.DynamicItem` works inside LayoutView (fix for Section landed in 2.6.x).

## 4. edit_message with a LayoutView
- `await interaction.response.edit_message(view=new_layout_view)` — **supported** (`interactions.py:519`, param typed `Optional[Union[View, LayoutView]]`); wholesale layout swap on click is the intended pattern. Same for `interaction.message.edit(view=...)`, `Webhook.edit_message`, and `InteractionMessage.edit`.
- Documented caveat (interactions.py docstring): when converting a message that previously had content/embeds/attachments to a LayoutView, "you must explicitly set the `content`, `embed`, `embeds`, and `attachments` parameters to `None`" (or `[]`). Not needed when the message was already CV2.
- Discord API constraint: once `IS_COMPONENTS_V2` is set on a message it cannot be unset — you can't edit a CV2 message back to plain content/embeds.

## 5. Limits enforced by the lib
- **40-component cap: yes, lib-enforced.** `discord/ui/view.py` lines 846/873/886: `raise ValueError('maximum number of children exceeded (40)')` — checked in `LayoutView.__init__`, `_add_count`, and `add_item`. The count is `total_children_count` and includes ALL nested descendants (Container=1 + each child; my test layout counted 12). It's a hardcoded literal `40`, no named constant.
- **Text cap: NOT enforced client-side.** `LayoutView.content_length()` sums all `TextDisplay.content`; docstring: "A view is allowed to have a maximum of 4000 display characters across all its items." Exceeding it -> Discord HTTP 400. Check `view.content_length() <= 4000` yourself.
- **ActionRow width: enforced.** A string Select has width 5 → **a Select and a Button cannot share one ActionRow** (`action_row.py:264` raises `ValueError('maximum number of children exceeded')`). Use two ActionRows. Max 5 buttons per row.
- Thumbnail description ≤ 256 chars; button label ≤ 80 (API-enforced).

## 6. Gotchas / known issues (2.6.x–2.7.x)
- **Issue #10335** (https://github.com/Rapptz/discord.py/issues/10335, reported vs 2.6.4, still open): nested items' `parent`/`view` were None and nested `interaction_check` skipped (a reporter shipped an auth bypass because Container checks silently didn't run). In 2.7.1 my introspection shows parent chains populated and `_run_checks` recursing — but re-verify your own check path; the issue is not formally closed.
- **`is_persistent()` doesn't recurse (verified in 2.7.1)**: a `LayoutView(timeout=None)` whose buttons have AUTO-GENERATED custom_ids still reports `is_persistent() == True` (Container inherits `Item.is_persistent`, which ignores nested children). `bot.add_view()` accepts it, but after a restart the regenerated custom_ids won't match the old message → "This interaction failed". **Always set explicit custom_id on every button/select.**
- 2.7.1 fixed: LayoutView memory leak on `remove_item`; earlier 2.6.x patches fixed `Section.children`/`accessory` parent=None, DynamicItem-in-Section errors, and inaccurate `total_children_count` with nested adds.
- `Section(...)` requires `accessory=` (TypeError without it). No plain-text `content` alongside a LayoutView — put text in `TextDisplay`.
- Container decorators define shared class-level state; instantiate a fresh view per message (standard View caveat).

## 7. Minimal runnable example (verified payload builds locally)
```python
import discord
from discord.ext import commands

MATCHES = {"1": "8500001 — 71 kills in 32 min", "2": "8500002 — fountain dive throw"}

class MatchContainer(discord.ui.Container):
    header = discord.ui.TextDisplay("# Herald matches worth reviewing")
    sep = discord.ui.Separator()
    row = discord.ui.ActionRow()

    @row.select(placeholder="Pick a match", custom_id="herald:pick",
                options=[discord.SelectOption(label=v, value=k) for k, v in MATCHES.items()])
    async def pick(self, interaction: discord.Interaction, select: discord.ui.Select):
        new = MatchView()
        new.container.header.content = f"# {MATCHES[select.values[0]]}"
        await interaction.response.edit_message(view=new)  # whole-layout swap

    row2 = discord.ui.ActionRow()
    @row2.button(label="Refresh", style=discord.ButtonStyle.primary, custom_id="herald:refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=MatchView())

class MatchView(discord.ui.LayoutView):  # timeout=None + custom_ids => persistent
    container = MatchContainer(accent_colour=discord.Colour.gold())
    def __init__(self):
        super().__init__(timeout=None)

intents = discord.Intents.default(); intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

@bot.event
async def setup_hook():
    bot.add_view(MatchView())  # re-register for persistence across restarts

@bot.command()
async def matches(ctx):
    await ctx.send(view=MatchView())  # no content= allowed with a LayoutView

bot.run("TOKEN")
```

Sources: introspection of `.venv/lib/python3.14/site-packages/discord/{ui/view.py,ui/container.py,ui/action_row.py,ui/thumbnail.py,abc.py,http.py,interactions.py}`; https://discordpy.readthedocs.io/en/stable/interactions/api.html; https://github.com/Rapptz/discord.py/blob/master/examples/views/layout.py; https://github.com/Rapptz/discord.py/blob/master/docs/whats_new.rst; https://github.com/Rapptz/discord.py/issues/10335; https://github.com/Rapptz/discord.py/pull/10166