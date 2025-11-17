#!/usr/bin/env python3
"""完整的端到端渲染测试：生成真实视频文件。

运行方式：
    python scripts/dev/e2e_full_render_test.py

测试流程：
1. 创建测试 mix 和歌词行
2. 添加候选片段
3. 锁定歌词行
4. 提交渲染任务
5. 等待渲染完成
6. 验证视频文件生成
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from twelvelabs import TwelveLabs

from src.domain.models.render_job import RenderJob
from src.domain.models.song_mix import LyricLine, SongMixRequest, VideoSegmentMatch
from src.infra.config.settings import get_settings
from src.infra.persistence.database import init_engine, init_models
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers.render_worker import render_mix


async def main() -> None:
    """主测试流程。"""
    print("=" * 80)
    print("完整端到端渲染测试：生成真实视频")
    print("=" * 80)
    print()

    # 初始化
    settings = get_settings()
    print(f"[1/9] 初始化数据库: {settings.postgres_dsn}")
    init_engine(settings.postgres_dsn)
    await init_models()
    print("✓ 数据库初始化完成\n")

    song_repo = SongMixRepository()
    render_repo = RenderJobRepository()

    # 创建测试 mix
    mix_id = str(uuid.uuid4())
    print(f"[2/9] 创建测试 mix: {mix_id}")
    mix = SongMixRequest(
        id=mix_id,
        song_title="完整渲染测试 - 观沧海",
        artist="曹操",
        source_type="upload",
        audio_asset_id="demo/caocao.mp3",
        lyrics_text="东临碣石，以观沧海。水何澹澹，山岛竦峙。",
        language="zh",
        timeline_status="pending",
        render_status="idle",
        owner_id="test-full-render-user",
    )
    await song_repo.create_request(mix)
    print(f"✓ Mix 创建成功: {mix.song_title}\n")

    # 创建歌词行
    print("[3/9] 创建歌词行")
    lines = [
        LyricLine(
            id=f"{mix_id}-line-1",
            mix_request_id=mix_id,
            line_no=1,
            original_text="东临碣石，以观沧海",
            start_time_ms=0,
            end_time_ms=3000,
            status="pending",
        ),
        LyricLine(
            id=f"{mix_id}-line-2",
            mix_request_id=mix_id,
            line_no=2,
            original_text="水何澹澹，山岛竦峙",
            start_time_ms=3500,
            end_time_ms=7000,
            status="pending",
        ),
        LyricLine(
            id=f"{mix_id}-line-3",
            mix_request_id=mix_id,
            line_no=3,
            original_text="树木丛生，百草丰茂",
            start_time_ms=7500,
            end_time_ms=11000,
            status="pending",
        ),
    ]
    await song_repo.bulk_insert_lines(lines)
    print(f"✓ 创建 {len(lines)} 行歌词\n")

    # 使用 TwelveLabs API 搜索真实的候选片段
    print("[4/9] 调用 TwelveLabs API 搜索候选视频片段")
    tl_client = TwelveLabs(api_key=settings.tl_api_key)
    candidates = []

    for line in lines:
        print(f"  搜索: {line.original_text}")
        try:
            search_results = tl_client.search.query(
                index_id=settings.tl_index_id,
                query_text=line.original_text,
                search_options=["visual"],
                page_limit=3,  # 每行取前3个候选
            )

            # SyncPager 需要直接迭代
            results_list = list(search_results)

            for rank, result in enumerate(results_list, 1):
                # TwelveLabs 返回的 result 直接包含 start/end，不是 clips 数组
                match = VideoSegmentMatch(
                    id=f"{mix_id}-match-{line.line_no}-{rank}",
                    line_id=line.id,
                    source_video_id=result.video_id,
                    index_id=settings.tl_index_id,
                    start_time_ms=int(result.start * 1000),  # 秒转毫秒
                    end_time_ms=int(result.end * 1000),
                    score=result.score,
                    generated_by="twelvelabs_api",
                )
                candidates.append(match)
                print(
                    f"    候选 {rank}: 视频 {result.video_id[:8]}..., "
                    f"{result.start:.1f}s-{result.end:.1f}s, 得分 {result.score:.2f}, "
                    f"置信度 {result.confidence}"
                )

        except Exception as e:
            print(f"    ⚠️  TwelveLabs 搜索失败: {e}")
            print("    使用 fallback 视频代替")
            # 使用 fallback 视频
            fallback_match = VideoSegmentMatch(
                id=f"{mix_id}-match-{line.line_no}-fallback",
                line_id=line.id,
                source_video_id=settings.fallback_video_id,
                index_id=settings.tl_index_id,
                start_time_ms=int((line.line_no - 1) * 3500),
                end_time_ms=int(line.line_no * 3500),
                score=0.5,
                generated_by="fallback",
            )
            candidates.append(fallback_match)

    if not candidates:
        print("❌ 没有找到任何候选片段")
        sys.exit(1)

    await song_repo.attach_candidates(candidates)
    print(f"✓ 添加 {len(candidates)} 个候选片段\n")

    # 锁定歌词行（为每行选择第一个候选）
    print("[5/9] 锁定歌词行")
    for line in lines:
        # 找到这一行的第一个候选
        line_candidates = [c for c in candidates if c.line_id == line.id]
        if line_candidates:
            line.status = "locked"
            line.selected_segment_id = line_candidates[0].id
            await song_repo.save_line(line)
            print(f"  第 {line.line_no} 行: 选择候选 {line_candidates[0].id}")
        else:
            print(f"  ⚠️  第 {line.line_no} 行: 没有候选片段，跳过")
    print("✓ 歌词行锁定完成\n")

    # 更新 timeline 状态
    await song_repo.update_timeline_status(mix_id, "generated")
    print("[6/9] Timeline 状态更新为 generated\n")

    # 提交渲染任务
    print("[7/9] 提交渲染任务")
    job_id = str(uuid.uuid4())
    job = RenderJob(
        id=job_id,
        mix_request_id=mix_id,
        job_status="queued",
        ffmpeg_script="",
    )
    await render_repo.save(job)
    print(f"✓ 渲染任务已创建: {job_id}")

    # 直接调用渲染 worker（同步模式，不使用 Redis 队列）
    print("  开始渲染...")
    await render_mix({}, job_id)
    print("✓ 渲染完成\n")

    # 检查渲染状态
    print("[8/9] 检查渲染状态")
    job = await render_repo.get(job_id)
    if job is None:
        print(f"❌ 找不到渲染任务: {job_id}")
        sys.exit(1)

    if job.job_status == "failed":
        print(f"❌ 渲染失败: {job.error_message}")
        sys.exit(1)
    elif job.job_status != "success":
        print(f"⚠️  渲染状态异常: {job.job_status}")
    else:
        print("✓ 渲染状态: success\n")

    # 验证结果
    print("[9/9] 验证渲染结果")
    job = await render_repo.get(job_id)
    assert job is not None
    assert job.job_status == "success"
    assert job.output_asset_id is not None

    output_path = Path(job.output_asset_id)
    print(f"  输出路径: {output_path}")

    # 检查文件是否存在
    if output_path.exists():
        file_size = output_path.stat().st_size
        print("✓ 视频文件已生成")
        print(f"  文件大小: {file_size / 1024:.2f} KB")
    else:
        print(f"❌ 视频文件不存在: {output_path}")
        sys.exit(1)

    # 显示 Render Metrics
    if job.metrics and "render" in job.metrics:
        print("\n" + "=" * 80)
        print("Render Metrics")
        print("=" * 80)
        print(json.dumps(job.metrics["render"], indent=2, ensure_ascii=False))
        print()

    # 最终总结
    print("=" * 80)
    print("🎉 完整渲染测试成功！")
    print("=" * 80)
    print(f"✅ Mix ID: {mix_id}")
    print(f"✅ Job ID: {job_id}")
    print(f"✅ 输出文件: {output_path}")
    print(f"✅ 文件大小: {file_size / 1024:.2f} KB")

    if job.metrics and "render" in job.metrics:
        metrics = job.metrics["render"]
        print(f"✅ 渲染行数: {metrics.get('line_count', 'N/A')}")
        print(f"✅ 平均对齐偏差: {metrics.get('avg_delta_ms', 'N/A'):.2f}ms")
        print(f"✅ 最大对齐偏差: {metrics.get('max_delta_ms', 'N/A'):.2f}ms")

    print()
    print("后续步骤：")
    print(f"1. 播放视频: open {output_path}")
    print(f"2. 查看任务: sqlite3 dev.db 'SELECT * FROM render_jobs WHERE id=\"{job_id}\"'")
    print()


if __name__ == "__main__":
    asyncio.run(main())
