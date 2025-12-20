"""多源歌词获取模块

支持多个歌词源，自动回退：
1. QQ音乐 - 版权最全（周杰伦等）
2. 网易云音乐 - 歌词质量高
3. 酷狗音乐 - 备用源
4. LRCLIB - 国际歌曲

使用方式：
    song, lyrics = await get_lyrics("说好不哭", "周杰伦")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence
from abc import ABC, abstractmethod

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LyricLine:
    """歌词行"""

    start_time: float  # 开始时间（秒）
    end_time: float | None  # 结束时间（秒），可能为None
    text: str  # 歌词文本


@dataclass
class SongInfo:
    """歌曲信息"""

    id: str
    name: str
    artist: str
    album: str | None = None
    duration_ms: int | None = None
    source: str = ""  # 来源平台


def parse_lrc_time(time_str: str) -> float:
    """解析LRC时间戳 [mm:ss.xx] -> 秒"""
    time_str = time_str.replace(":", ".", 1)
    parts = time_str.split(".")

    if len(parts) >= 2:
        minutes = int(parts[0])
        seconds = int(parts[1]) if len(parts[1]) <= 2 else int(parts[1])
        if len(parts) >= 3:
            ms_str = parts[2]
            if len(ms_str) == 2:
                ms_str += "0"
            elif len(ms_str) == 1:
                ms_str += "00"
            milliseconds = int(ms_str[:3])
        else:
            milliseconds = 0
        return minutes * 60 + seconds + milliseconds / 1000
    else:
        return float(time_str)


def parse_lrc(lrc_text: str) -> list[LyricLine]:
    """解析LRC歌词文本"""
    if not lrc_text:
        return []

    lines = []
    pattern = r"\[(\d{1,2}:\d{1,2}[.:]\d{1,3})\](.+?)(?=\[|$)"

    for match in re.finditer(pattern, lrc_text, re.DOTALL):
        time_str = match.group(1)
        text = match.group(2).strip()

        # 跳过空行和元数据行
        if not text or any(
            text.startswith(prefix) for prefix in ["作词", "作曲", "编曲", "制作", "混音", "母带"]
        ):
            continue

        try:
            start_time = parse_lrc_time(time_str)
            lines.append(LyricLine(start_time=start_time, end_time=None, text=text))
        except (ValueError, IndexError):
            continue

    # 按时间排序
    lines.sort(key=lambda x: x.start_time)

    # 计算结束时间
    for i in range(len(lines) - 1):
        lines[i].end_time = lines[i + 1].start_time

    if lines:
        lines[-1].end_time = lines[-1].start_time + 5.0

    return lines


# ============ 歌词源基类 ============


class LyricsSource(ABC):
    """歌词源基类"""

    name: str = "base"

    @abstractmethod
    async def search(self, keyword: str, limit: int = 5) -> list[SongInfo]:
        """搜索歌曲"""
        pass

    @abstractmethod
    async def get_lyrics(self, song: SongInfo) -> str | None:
        """获取歌词"""
        pass


# ============ QQ音乐 ============


class QQMusicSource(LyricsSource):
    """QQ音乐歌词源 - 版权最全"""

    name = "QQ音乐"

    async def search(self, keyword: str, limit: int = 5) -> list[SongInfo]:
        url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
        params: dict[str, str | int] = {
            "w": keyword,
            "format": "json",
            "p": 1,
            "n": limit,
        }
        headers = {
            "Referer": "https://y.qq.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                songs = []
                for s in data.get("data", {}).get("song", {}).get("list", []):
                    singers = ", ".join([x.get("name", "") for x in s.get("singer", [])])
                    songs.append(
                        SongInfo(
                            id=s.get("songmid", ""),
                            name=s.get("songname", ""),
                            artist=singers,
                            album=s.get("albumname"),
                            duration_ms=s.get("interval", 0) * 1000,
                            source=self.name,
                        )
                    )

                logger.info("lyrics.qq.search", keyword=keyword, results=len(songs))
                return songs

            except Exception as e:
                logger.error("lyrics.qq.search_error", keyword=keyword, error=str(e))
                return []

    async def get_lyrics(self, song: SongInfo) -> str | None:
        url = "https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
        params: dict[str, str | int] = {
            "songmid": song.id,
            "format": "json",
            "nobase64": 1,
        }
        headers = {
            "Referer": "https://y.qq.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                lyric = data.get("lyric", "")
                if lyric:
                    logger.info("lyrics.qq.fetch", song_id=song.id, length=len(lyric))
                    return str(lyric)

                logger.warning("lyrics.qq.not_found", song_id=song.id)
                return None

            except Exception as e:
                logger.error("lyrics.qq.fetch_error", song_id=song.id, error=str(e))
                return None


# ============ 网易云音乐 ============


class NeteaseMusicSource(LyricsSource):
    """网易云音乐歌词源"""

    name = "网易云"

    async def search(self, keyword: str, limit: int = 5) -> list[SongInfo]:
        url = "https://music.163.com/api/search/get"
        params: dict[str, str | int] = {
            "s": keyword,
            "type": 1,
            "limit": limit,
            "offset": 0,
        }
        headers = {
            "Referer": "https://music.163.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                songs = []
                for s in data.get("result", {}).get("songs", []):
                    artists = s.get("artists", [])
                    artist_name = (
                        ", ".join(a.get("name", "") for a in artists) if artists else "未知"
                    )
                    songs.append(
                        SongInfo(
                            id=str(s.get("id")),
                            name=s.get("name", ""),
                            artist=artist_name,
                            album=s.get("album", {}).get("name"),
                            duration_ms=s.get("duration"),
                            source=self.name,
                        )
                    )

                logger.info("lyrics.netease.search", keyword=keyword, results=len(songs))
                return songs

            except Exception as e:
                logger.error("lyrics.netease.search_error", keyword=keyword, error=str(e))
                return []

    async def get_lyrics(self, song: SongInfo) -> str | None:
        url = "https://music.163.com/api/song/lyric"
        params: dict[str, str | int] = {
            "id": song.id,
            "lv": 1,
            "tv": 1,
        }
        headers = {
            "Referer": "https://music.163.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                lrc: str | None = data.get("lrc", {}).get("lyric")
                if lrc:
                    logger.info("lyrics.netease.fetch", song_id=song.id, length=len(lrc))
                    return lrc

                tlyric: str | None = data.get("tlyric", {}).get("lyric")
                if tlyric:
                    return tlyric

                logger.warning("lyrics.netease.not_found", song_id=song.id)
                return None

            except Exception as e:
                logger.error("lyrics.netease.fetch_error", song_id=song.id, error=str(e))
                return None


# ============ 酷狗音乐 ============


class KugouMusicSource(LyricsSource):
    """酷狗音乐歌词源"""

    name = "酷狗"

    async def search(self, keyword: str, limit: int = 5) -> list[SongInfo]:
        url = "https://mobileservice.kugou.com/api/v3/search/song"
        params: dict[str, str | int] = {
            "keyword": keyword,
            "page": 1,
            "pagesize": limit,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                songs = []
                for s in data.get("data", {}).get("info", []):
                    songs.append(
                        SongInfo(
                            id=s.get("hash", ""),
                            name=s.get("songname", ""),
                            artist=s.get("singername", ""),
                            album=s.get("album_name"),
                            duration_ms=s.get("duration", 0) * 1000,
                            source=self.name,
                        )
                    )

                logger.info("lyrics.kugou.search", keyword=keyword, results=len(songs))
                return songs

            except Exception as e:
                logger.error("lyrics.kugou.search_error", keyword=keyword, error=str(e))
                return []

    async def get_lyrics(self, song: SongInfo) -> str | None:
        # 酷狗需要先获取歌词候选列表
        search_url = "https://krcs.kugou.com/search"
        params: dict[str, str | int] = {
            "ver": 1,
            "man": "yes",
            "client": "mobi",
            "hash": song.id,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(search_url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning("lyrics.kugou.no_candidates", song_id=song.id)
                    return None

                # 获取第一个候选歌词
                candidate = candidates[0]
                lyric_id = candidate.get("id")
                access_key = candidate.get("accesskey")

                if not lyric_id or not access_key:
                    return None

                # 下载歌词
                download_url = "https://lyrics.kugou.com/download"
                download_params = {
                    "ver": 1,
                    "client": "pc",
                    "id": lyric_id,
                    "accesskey": access_key,
                    "fmt": "lrc",
                    "charset": "utf8",
                }

                resp = await client.get(
                    download_url, params=download_params, headers=headers, timeout=10
                )
                resp.raise_for_status()
                lyric_data = resp.json()

                # 歌词是base64编码的
                import base64

                content = lyric_data.get("content", "")
                if content:
                    lyric = base64.b64decode(content).decode("utf-8")
                    logger.info("lyrics.kugou.fetch", song_id=song.id, length=len(lyric))
                    return lyric

                logger.warning("lyrics.kugou.not_found", song_id=song.id)
                return None

            except Exception as e:
                logger.error("lyrics.kugou.fetch_error", song_id=song.id, error=str(e))
                return None


# ============ LRCLIB (国际歌曲) ============


class LrclibSource(LyricsSource):
    """LRCLIB歌词源 - 免费国际歌词库"""

    name = "LRCLIB"

    async def search(self, keyword: str, limit: int = 5) -> list[SongInfo]:
        url = "https://lrclib.net/api/search"
        params = {"q": keyword}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, headers=headers, timeout=10)
                resp.raise_for_status()
                results = resp.json()

                songs = []
                for r in results[:limit]:
                    songs.append(
                        SongInfo(
                            id=str(r.get("id", "")),
                            name=r.get("trackName", ""),
                            artist=r.get("artistName", ""),
                            album=r.get("albumName"),
                            duration_ms=int(r.get("duration", 0) * 1000),
                            source=self.name,
                        )
                    )

                logger.info("lyrics.lrclib.search", keyword=keyword, results=len(songs))
                return songs

            except Exception as e:
                logger.error("lyrics.lrclib.search_error", keyword=keyword, error=str(e))
                return []

    async def get_lyrics(self, song: SongInfo) -> str | None:
        url = f"https://lrclib.net/api/get/{song.id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                data = resp.json()

                # 优先同步歌词
                lyric = data.get("syncedLyrics") or data.get("plainLyrics")
                if lyric:
                    logger.info("lyrics.lrclib.fetch", song_id=song.id, length=len(lyric))
                    return str(lyric)

                logger.warning("lyrics.lrclib.not_found", song_id=song.id)
                return None

            except Exception as e:
                logger.error("lyrics.lrclib.fetch_error", song_id=song.id, error=str(e))
                return None


# ============ 多源聚合 ============

# 默认歌词源顺序（QQ音乐版权最全，放第一位）
DEFAULT_SOURCES: list[LyricsSource] = [
    QQMusicSource(),
    NeteaseMusicSource(),
    KugouMusicSource(),
    LrclibSource(),
]


def _match_song(songs: list[SongInfo], song_name: str, artist: str | None) -> SongInfo | None:
    """匹配最佳歌曲"""
    if not songs:
        return None

    best_match = songs[0]

    for song in songs:
        # 完全匹配歌名和歌手
        if song.name == song_name and artist and artist in song.artist:
            return song
        # 完全匹配歌名
        if song.name == song_name:
            best_match = song
        # 包含歌名
        elif song_name in song.name and best_match.name != song_name:
            best_match = song

    return best_match


async def get_lyrics(
    song_name: str,
    artist: str | None = None,
    sources: list[LyricsSource] | None = None,
) -> tuple[SongInfo | None, list[LyricLine]]:
    """从多个源获取歌词（自动回退）

    Args:
        song_name: 歌曲名
        artist: 歌手名（可选，提高匹配准确度）
        sources: 自定义歌词源列表，默认使用所有源

    Returns:
        (歌曲信息, 解析后的歌词列表)
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    keyword = f"{song_name} {artist}" if artist else song_name

    for source in sources:
        try:
            logger.info("lyrics.trying_source", source=source.name, keyword=keyword)

            # 搜索歌曲
            songs = await source.search(keyword, limit=5)
            if not songs:
                logger.info("lyrics.source_no_results", source=source.name)
                continue

            # 匹配最佳结果
            best_match = _match_song(songs, song_name, artist)
            if not best_match:
                continue

            logger.info(
                "lyrics.source_match",
                source=source.name,
                matched=f"{best_match.name} - {best_match.artist}",
            )

            # 获取歌词
            lrc_text = await source.get_lyrics(best_match)
            if not lrc_text:
                logger.info("lyrics.source_no_lyrics", source=source.name)
                continue

            # 解析歌词
            lyrics = parse_lrc(lrc_text)
            if not lyrics:
                logger.info("lyrics.source_parse_failed", source=source.name)
                continue

            logger.info(
                "lyrics.success",
                source=source.name,
                song=f"{best_match.name} - {best_match.artist}",
                lines=len(lyrics),
            )

            return best_match, lyrics

        except Exception as e:
            logger.error("lyrics.source_error", source=source.name, error=str(e))
            continue

    logger.warning("lyrics.all_sources_failed", song_name=song_name, artist=artist)
    return None, []


def lyrics_to_segments(lyrics: Sequence[LyricLine]) -> list[dict]:
    """将歌词转换为与Whisper兼容的segment格式"""
    return [
        {
            "start": line.start_time,
            "end": line.end_time or line.start_time + 3.0,
            "text": line.text,
        }
        for line in lyrics
    ]


# ============ 命令行测试 ============

if __name__ == "__main__":
    import asyncio
    import sys

    async def main() -> None:
        if len(sys.argv) < 2:
            print("Usage: python -m src.lyrics.fetcher <歌曲名> [歌手名]")
            sys.exit(1)

        song_name = sys.argv[1]
        artist = sys.argv[2] if len(sys.argv) > 2 else None

        print(f"\n搜索: {song_name}" + (f" - {artist}" if artist else ""))
        print("=" * 60)

        song, lyrics = await get_lyrics(song_name, artist)

        if song:
            print(f"匹配歌曲: {song.name} - {song.artist}")
            print(f"来源: {song.source}")
            print(f"歌曲ID: {song.id}")
            print("=" * 60)

        if lyrics:
            print(f"\n歌词 ({len(lyrics)} 句):\n")
            for line in lyrics:
                end_str = f"{line.end_time:.2f}" if line.end_time else "?"
                print(f"[{line.start_time:6.2f} - {end_str:>6}] {line.text}")
        else:
            print("未找到歌词")

    asyncio.run(main())
