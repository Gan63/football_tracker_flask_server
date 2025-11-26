import os
import traceback

# Import your processing function from main.py
# main.py must define: def process_video_optimized(input_path, output_path)
from main import process_video_optimized

class FootballTrackerAPI:
    """
    Lightweight wrapper so existing code (flask_api.py / mcp_server.py)
    can `from football_core import tracker_api` and call:
        tracker_api.process_video_safe(input_path)
    """

    def __init__(self):
        # make sure output folder exists
        os.makedirs("output", exist_ok=True)

    def process_video_safe(self, input_path):
        """
        Runs your process_video_optimized pipeline and returns a dict
        in the shape other parts of your app expect.
        """
        try:
            # set output filename (unique per run if you want)
            base = os.path.splitext(os.path.basename(input_path))[0]
            output_filename = f"{base}_processed.mp4"
            output_path = os.path.join("output", output_filename)

            # Run the pipeline (this should raise on error)
            process_video_optimized(input_path, output_path)

            # Return minimal success payload (adjust if your app expects more)
            return {
                "processed_video_url": output_filename,
                "status": "success",
                "message": "Processing finished",
            }

        except Exception as e:
            # Log traceback and return an error dict (so caller sees failure)
            tb = traceback.format_exc()
            print("Error in process_video_safe:", tb)
            return {
                "status": "error",
                "message": str(e),
                "traceback": tb
            }

# single shared instance imported by flask_api.py and others
tracker_api = FootballTrackerAPI()
