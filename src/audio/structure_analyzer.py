"""音乐结构分析模块 - 基于歌词时长检测 intro/outro"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def detect_intro_outro_boundaries(
    lyrics_lines: list[dict],
    audio_duration_ms: int = 0,
    min_lyric_duration_ms: int = 1000,
) -> tuple[int, int]:
    """基于歌词时长检测 intro/outro 边界。

    规则：时长 >= min_lyric_duration_ms 的歌词行被认为是"真正歌词"。
    开头连续的短行（< min_lyric_duration_ms）会被合并为 Intro。
    结尾连续的短行会被合并为 Outro。

    Args:
        lyrics_lines: 歌词行列表，格式 [{"text": "...", "start_ms": int, "end_ms": int}, ...]
        audio_duration_ms: 音频总时长（毫秒）
        min_lyric_duration_ms: 最小歌词时长阈值（默认 1000ms）

    Returns:
        (intro_end_ms, outro_start_ms) 边界时间
    """
    if not lyrics_lines:
        return 0, audio_duration_ms

    # 找到第一句"真正歌词"的开始时间
    first_real_lyric_start_ms = lyrics_lines[0]["start_ms"]
    for line in lyrics_lines:
        duration = line["end_ms"] - line["start_ms"]
        if duration >= min_lyric_duration_ms:
            first_real_lyric_start_ms = line["start_ms"]
            break

    # 找到最后一句"真正歌词"的结束时间
    last_real_lyric_end_ms = lyrics_lines[-1]["end_ms"]
    for line in reversed(lyrics_lines):
        duration = line["end_ms"] - line["start_ms"]
        if duration >= min_lyric_duration_ms:
            last_real_lyric_end_ms = line["end_ms"]
            break

    intro_end_ms = first_real_lyric_start_ms
    outro_start_ms = last_real_lyric_end_ms

    # 确保 outro_start 不超过音频时长
    if audio_duration_ms > 0:
        outro_start_ms = min(outro_start_ms, audio_duration_ms)

    logger.info(
        "structure_analyzer.boundaries_detected",
        first_real_lyric_start_ms=first_real_lyric_start_ms,
        last_real_lyric_end_ms=last_real_lyric_end_ms,
        intro_end_ms=intro_end_ms,
        outro_start_ms=outro_start_ms,
        audio_duration_ms=audio_duration_ms,
    )

    return intro_end_ms, outro_start_ms


def merge_intro_outro_lines(
    lyrics_lines: list[dict],
    intro_end_ms: int,
    outro_start_ms: int,
    audio_duration_ms: int = 0,
) -> list[dict]:
    """合并 intro/outro 范围内的歌词行。

    边界规则（以歌词时间戳为准）：
    - 歌词行完全在 intro 范围内（end_ms <= intro_end_ms）→ 合并到 (Intro)
    - 歌词行跨越 intro 边界 → 保留为主体歌词
    - 歌词行完全在主体范围内 → 保留为主体歌词
    - 歌词行跨越 outro 边界 → 保留为主体歌词
    - 歌词行完全在 outro 范围内（start_ms >= outro_start_ms）→ 合并到 (Outro)

    Args:
        lyrics_lines: 原始歌词行列表
        intro_end_ms: intro 结束时间
        outro_start_ms: outro 开始时间
        audio_duration_ms: 音频总时长

    Returns:
        合并后的歌词行列表
    """
    if not lyrics_lines:
        return []

    merged: list[dict] = []
    intro_lines: list[dict] = []
    main_lines: list[dict] = []
    outro_lines: list[dict] = []

    for line in lyrics_lines:
        start_ms = line["start_ms"]
        end_ms = line["end_ms"]

        # 判断歌词行所属区域
        if end_ms <= intro_end_ms:
            # 完全在 intro 范围内
            intro_lines.append(line)
        elif start_ms >= outro_start_ms:
            # 完全在 outro 范围内
            outro_lines.append(line)
        else:
            # 主体歌词（包括跨越边界的情况）
            main_lines.append(line)

    # 合并 intro 行（只有当 intro_end_ms > 0 且有行被合并时）
    if intro_lines and intro_end_ms > 0:
        merged.append(
            {
                "text": "(Intro)",
                "start_ms": 0,
                "end_ms": intro_end_ms,
                "is_instrumental": True,
            }
        )
        logger.info(
            "structure_analyzer.merged_intro",
            original_lines=len(intro_lines),
            merged_texts=[line["text"][:20] for line in intro_lines],
            intro_end_ms=intro_end_ms,
        )

    # 添加主体歌词
    merged.extend(main_lines)

    # 合并 outro 行（只有当有 outro 空间时）
    final_end_ms = audio_duration_ms if audio_duration_ms > 0 else lyrics_lines[-1]["end_ms"]
    if outro_start_ms < final_end_ms:
        # 只有当有歌词行被合并，或者有明显的尾奏空间时才添加 (Outro)
        if outro_lines or (final_end_ms - outro_start_ms > 1000):
            merged.append(
                {
                    "text": "(Outro)",
                    "start_ms": outro_start_ms,
                    "end_ms": final_end_ms,
                    "is_instrumental": True,
                }
            )
            logger.info(
                "structure_analyzer.merged_outro",
                original_lines=len(outro_lines),
                merged_texts=[line["text"][:20] for line in outro_lines] if outro_lines else [],
                outro_start_ms=outro_start_ms,
                final_end_ms=final_end_ms,
            )

    return merged
