import numpy as np

from vision_processor import analyze_frame, decode_frame, generate_mock_frame


def test_opencv_demo_returns_depth_annotation_and_decodable_image() -> None:
    frame = generate_mock_frame(cycle=2)
    result = analyze_frame(frame, cycle=2, use_yolo=False)
    decoded = decode_frame(result.annotated_frame_base64)

    assert result.detector_mode == "opencv-simulation"
    assert result.flooding_depth_cm > 0
    assert 0 < result.water_mask_ratio < 1
    assert len(result.detected_objects) == 3
    assert np.asarray(decoded).shape[:2] == frame.shape[:2]
    assert any(item.flooded for item in result.detected_objects)
