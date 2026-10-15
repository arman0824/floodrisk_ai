# Optional model assets

Place a pre-downloaded `yolov8n.pt` file in this directory to enable optional
vehicle detection. The demo never downloads weights at runtime. Without the
file, `vision_processor.py` uses its deterministic OpenCV simulation and the
rest of the application remains fully functional.
