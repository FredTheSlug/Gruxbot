# Gruxbot

Discord bot for **Predecessor** stats using **[pred.gg](https://pred.gg)** GraphQL, with an optional **[omeda.city](https://omeda.city)** REST fallback for player search and match history.

## Features

- `/player` — look up a player by name or UUID; show recent matches
- `/hero` — resolve a hero from `/heroes.json` and show dashboard stats when available
- `/build` — top 3 core items and top 3 crests for a hero and role (Ranked · Paragon · current patch, via pred.gg)
- `/item` — resolve an item from `/items.json`
- `/follow` / `/unfollow` / `/following` — poll match history and post new-match notifications in-channel
- `/followcheck` — run the follow check immediately (posts any missed notifications)

pred.gg exposes a public GraphQL IDE at [pred.gg/gql](https://pred.gg/gql). Heroes, items, and single-match lookups work without auth. **Player search** and **match history** (`playersPaginated`, `matchesPaginated`) require OAuth2.

### OAuth2 setup (PKCE)

When you create your pred.gg application, set the **callback / redirect URI** to:

```text
http://127.0.0.1:8765/callback
```

It must match exactly (including `http`, not `https`).

1. Set environment variables:

   ```powershell
   $env:PRED_OAUTH_CLIENT_ID="your_client_id"
   $env:PRED_OAUTH_CLIENT_SECRET="your_client_secret"
   $env:PRED_OAUTH_SCOPE="read"
   ```

   (`read` is the pred.gg OAuth scope; it is the default if omitted.)

2. Sign in at https://pred.gg/login, then log in once via PKCE (saves tokens to `data/oauth_tokens.json`):

   ```powershell
   python -m pred_bot.auth
   ```

3. Start the bot as usual. Tokens refresh automatically.

Without OAuth, the bot falls back to omeda.city’s legacy JSON endpoints for player search and match history (`STATS_USE_OMEDA_FALLBACK=true`, default). `/build` requires pred.gg OAuth (same tokens as match history).

### `/build` (hero core items + crests)

Uses pred.gg `hero.coreBuild` GraphQL (same data as hero pages, e.g. `https://pred.gg/heroes/boris?gameModes=RANKED&role=JUNGLE&ranks=36`). Filters are fixed to **Ranked** and **Paragon** for the current season patch.

## Requirements

- Python 3.11+ (tested on 3.13)
- A [Discord application](https://discord.com/developers/applications) with a bot user and token

## Setup

1. Clone or copy this `pred-bot` folder.

2. Create a virtual environment and install:

   ```powershell
   cd pred-bot
   py -m venv .venv
   .\.venv\Scripts\pip install -e ".[dev]"
   ```

3. Copy `.env.example` to `.env` (or set variables in your host environment). At minimum set `DISCORD_BOT_TOKEN`.

4. **Discord Developer Portal**

   - Create an application → **Bot** → reset token → paste into `DISCORD_BOT_TOKEN`
   - Enable **Privileged Gateway Intents** only if you later add features that need them (slash commands alone do not require Message Content Intent)
   - **OAuth2 → URL Generator**: scopes `bot`, `applications.commands`; bot permissions at least **Send Messages**, **Embed Links**, **Use Slash Commands** (and **Read Messages/View Channels** as appropriate)

5. Run:

   ```powershell
   $env:DISCORD_BOT_TOKEN="your_token_here"
   .\.venv\Scripts\python -m pred_bot
   ```

   Or use the console script after install:

   ```powershell
   .\.venv\Scripts\pred-bot
   ```

### Faster slash-command sync during development

Set `GUILD_ID` to your test server ID. The bot will `copy_global_to` that guild and sync there (updates appear quickly). Omit `GUILD_ID` for global commands (can take up to an hour to propagate).

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | — | **Required** |
| `PRED_GQL_URL` | `https://pred.gg/gql` | pred.gg GraphQL endpoint |
| `PRED_OAUTH_CLIENT_ID` | — | OAuth app client id |
| `PRED_OAUTH_CLIENT_SECRET` | — | OAuth app client secret |
| `PRED_OAUTH_REDIRECT_URI` | `http://127.0.0.1:8765/callback` | Must match pred.gg app settings |
| `PRED_OAUTH_SCOPE` | `read` | Required for pred.gg authorize |
| `OAUTH_TOKEN_PATH` | `data/oauth_tokens.json` | Saved tokens after `python -m pred_bot.auth` |
| `PRED_GQL_AUTHORIZATION` | — | Optional static `Bearer …` (skips OAuth file) |
| `STATS_WEB_BASE_URL` | `https://pred.gg` | Links in embeds |
| `STATS_USE_OMEDA_FALLBACK` | `true` | Use omeda.city REST when pred.gg returns Forbidden |
| `OMEDA_BASE_URL` | `https://omeda.city` | Legacy fallback API base |
| `FOLLOW_POLL_SECONDS` | `120` | Poll interval for `/follow` |
| `DATABASE_PATH` | `data/follows.sqlite3` | SQLite file for follows |
| `GUILD_ID` | — | Optional guild for command sync |
| `HTTP_MAX_CONCURRENCY` | `5` | Max concurrent Omeda requests |
| `HTTP_MAX_RETRIES` | `3` | Retries for timeouts / 5xx |
| `FOLLOW_POLL_DEBUG` | off | Set `1` to print DEBUG lines when a followed player has no new match vs. last poll |

## Troubleshooting `/follow` notifications

1. **Ingest delays** — Finished games can take several minutes to appear on pred.gg / omeda.city. The bot only notifies once match history updates.

2. **Correct player UUID** — `/follow` must use the profile ID from the player’s pred.gg URL (`https://pred.gg/players/{uuid}`).

3. **Baseline after `/follow`** — The bot records your latest match at follow time and only notifies when a **newer** match appears. It does not post for games that finished before that baseline.

4. **Permissions** — The bot needs **Send Messages** and **Embed Links** in the channel where you ran `/follow`. If it cannot resolve the channel (deleted channel, missing access), check the console for warnings.

5. **Verbose polling logs** — Run with `$env:FOLLOW_POLL_DEBUG="1"` before starting the bot. You should see DEBUG lines when the newest match ID has not changed since the last poll.

6. **Force a check** — Run `/followcheck` in the same channel where you used `/follow`. If Omeda has newer matches than the stored baseline, the bot posts them immediately and reports status in an ephemeral reply.

## Tests

```powershell
.\.venv\Scripts\pytest -v
```

## References

- [pred.gg GraphQL IDE](https://pred.gg/gql)
- [pred.gg forum — API auth / Forbidden](https://forums.pred.gg/t/api-request-help/306)
- [narb.app](https://www.narb.app/) (companion bot UX reference)

## License

Apache-2.0 (match your monorepo policy if different).
