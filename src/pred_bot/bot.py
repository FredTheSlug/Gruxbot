"""Discord bot application."""

from __future__ import annotations

import asyncio
import logging

import discord
import httpx
from discord.ext import commands

from pred_bot.config import Config
from pred_bot.follow_poller import FollowPoller
from pred_bot.follow_store import FollowStore
from pred_bot.omeda_client import OmedaClient
from pred_bot.oauth_tokens import OAuthTokenStore
from pred_bot.pred_client import PredGqlClient
from pred_bot.stats_client import StatsClient

log = logging.getLogger(__name__)


class PredBot(commands.Bot):
    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.config = config
        self.http_client: httpx.AsyncClient
        self.stats: StatsClient
        self.follow_store = FollowStore(config.database_path)
        self.poller = FollowPoller(self)

    async def setup_hook(self) -> None:
        await self.follow_store.init()
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        oauth_store = OAuthTokenStore(self.config.oauth_token_path)
        has_tokens = oauth_store.load() is not None
        has_oauth_creds = bool(
            self.config.pred_oauth_client_id and self.config.pred_oauth_client_secret
        )
        if not has_oauth_creds and not has_tokens and not self.config.pred_gql_authorization:
            oauth_store = None
        elif has_tokens and not has_oauth_creds:
            log.warning(
                "pred.gg tokens at %s but PRED_OAUTH_CLIENT_ID/SECRET missing — "
                "using access token only until it expires (refresh disabled)",
                self.config.oauth_token_path,
            )
        elif has_oauth_creds and not has_tokens and not self.config.pred_gql_authorization:
            log.warning(
                "pred.gg OAuth configured but no tokens at %s — run: python -m pred_bot.auth",
                self.config.oauth_token_path,
            )
        pred = PredGqlClient(
            self.config.pred_gql_url,
            authorization=self.config.pred_gql_authorization,
            build_authorization=self.config.pred_gql_build_authorization,
            oauth_store=oauth_store,
            oauth_client_id=self.config.pred_oauth_client_id,
            oauth_client_secret=self.config.pred_oauth_client_secret,
            oauth_token_url=self.config.pred_oauth_token_url,
            max_concurrency=self.config.http_max_concurrency,
            max_retries=self.config.http_max_retries,
        )
        omeda = (
            OmedaClient(
                self.config.omeda_base_url,
                max_concurrency=self.config.http_max_concurrency,
                max_retries=self.config.http_max_retries,
            )
            if self.config.use_omeda_fallback
            else None
        )
        self.stats = StatsClient(
            pred=pred,
            omeda=omeda,
            use_omeda_fallback=self.config.use_omeda_fallback,
            web_base_url=self.config.stats_web_base_url,
        )
        if self.config.use_omeda_fallback:
            log.info(
                "Stats API: pred.gg GraphQL (%s) with omeda.city fallback for gated player/match lists",
                self.config.pred_gql_url,
            )
        else:
            log.info("Stats API: pred.gg GraphQL only (%s)", self.config.pred_gql_url)

        from pred_bot.commands import build, follow, hero, item, match, player

        player.register(self)
        hero.register(self)
        item.register(self)
        build.register(self)
        follow.register(self)
        match.register(self)

        command_names = sorted(c.name for c in self.tree.get_commands())
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(
                "Synced %s command(s) to guild %s: %s",
                len(synced),
                self.config.guild_id,
                ", ".join(f"/{c.name}" for c in synced) or "(none)",
            )
        else:
            synced = await self.tree.sync()
            log.info(
                "Synced %s global command(s) (Discord may take up to ~1 hour to show them): %s",
                len(synced),
                ", ".join(f"/{c.name}" for c in synced) or "(none)",
            )
        if "lastmatch" not in command_names:
            log.warning("lastmatch is not registered on the command tree")

        self.poller.start()

        if self.config.follow_poll_debug:
            logging.getLogger("pred_bot.follow_poller").setLevel(logging.DEBUG)

    async def close(self) -> None:
        if hasattr(self, "http_client"):
            await self.http_client.aclose()
        await super().close()


async def _runner() -> None:
    from pred_bot.logging import setup_logging

    setup_logging()
    config = Config()
    bot = PredBot(config)
    async with bot:
        await bot.start(config.discord_token)


def run() -> None:
    asyncio.run(_runner())
