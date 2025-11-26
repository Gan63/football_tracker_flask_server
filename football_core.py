from main import process_video_optimized

class FootballTrackerAPI:
    def process_video_safe(self, input_path):
        output_path = "output/processed_mcp.mp4"
        return process_video_optimized(input_path, output_path)

# THIS is the object flask_api and mcp_server import
tracker_api = FootballTrackerAPI()
