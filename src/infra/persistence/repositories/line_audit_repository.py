"""歌词行审计记录仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.domain.models.song_mix import LyricLine
from src.infra.persistence.database import get_session


class LineAuditRepository:
    async def append_entry(self, line_id: str, entry: dict[str, Any]) -> None:
        async with get_session() as session:
            line = await session.get(LyricLine, line_id)
            if line is None:
                raise ValueError("Lyric line not found")
            log = list(line.audit_log or [])
            log.append({"timestamp": datetime.utcnow().isoformat(), **entry})
            line.audit_log = log
            session.add(line)
            await session.commit()
