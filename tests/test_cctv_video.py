from pathlib import Path

from vision_processor import analyze_video_frame


def test_supplied_cctv_clip_produces_a_live_frame() -> None:
    video_path = Path("car_flood.mp4")
    assert video_path.is_file()

    result = analyze_video_frame(str(video_path), cycle=2, use_yolo=False)

    assert result.source == "provided-cctv:car_flood.mp4"
    assert result.flooding_depth_cm > 0
    assert result.frame_width > 0
    assert result.frame_height > 0
