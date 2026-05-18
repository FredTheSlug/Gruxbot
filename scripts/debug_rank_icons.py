"""Debug rank icon fetch + render for a match."""
import asyncio
import io
import logging
import sys

import httpx

logging.basicConfig(level=logging.DEBUG)

from pred_bot.config import Config
from pred_bot.hero_portraits import portrait_url
from pred_bot.match_detail import parse_pred_match
from pred_bot.omeda_client import OmedaClient
from pred_bot.pred_client import PredGqlClient
from pred_bot.scoreboard_render import (
    _player_key,
    fetch_rank_icons,
    render_scoreboard_png,
)
from pred_bot.stats_client import StatsClient

MID = "9d1794a79dae4c3ca4d32f8d1d8913df"


async def main() -> None:
    config = Config()
    pred = PredGqlClient(config.pred_gql_url, authorization=config.pred_gql_authorization)
    omeda = OmedaClient(config.omeda_base_url) if config.use_omeda_fallback else None
    stats = StatsClient(pred=pred, omeda=omeda, use_omeda_fallback=config.use_omeda_fallback)

    async with httpx.AsyncClient(timeout=60.0) as client:
        raw = await pred.get_match(client, MID)
        detail = parse_pred_match(raw)
        if not detail:
            print("parse failed")
            return

        await stats._enrich_player_ranks(client, detail)

        for p in detail.players[:5]:
            key = _player_key(p)
            url = portrait_url(p.rank_icon, base=stats.web_base_url)
            print(
                f"{p.name!r} key={key!r} rank={p.rank_name!r} "
                f"icon={p.rank_icon!r} url={url}"
            )

        rank_icons = await fetch_rank_icons(client, detail.players, base_url=stats.web_base_url)
        print(f"fetched rank icons for {len(rank_icons)} players: {list(rank_icons.keys())}")

        for key, img in list(rank_icons.items())[:2]:
            print(f"  {key}: size={img.size} mode={img.mode}")

        from pred_bot.scoreboard_render import fetch_portraits

        portraits = await fetch_portraits(client, detail.players, base_url=stats.web_base_url)
        png = render_scoreboard_png(detail, portraits=portraits, rank_icons=rank_icons)
        out = "data/debug_scoreboard.png"
        with open(out, "wb") as f:
            f.write(png)
        print(f"wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
