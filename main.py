from utils import *
from trackers import *
from team_assigner import *
from player_ball_assigner import *
from camera_movement import *
from view_transformation import *
from speed_and_distance import *
import numpy as np
import cv2
import os
import gc

os.environ["LOKY_MAX_CPU_COUNT"] = "4"


def process_video_optimized(input_path,output_path):
        try:
            print("Initializing tracker...")
            tracker = Tracker('models/yolov5su.pt')

            print("Tracking objects...")
            tracks = tracker.get_object_tracks(
                read_video_frames(input_path),
                read_from_stub=False,
                stub_path='stubs/track_stubs.pkl'
            )
            tracker.add_position_to_tracks(tracks)

            print("Interpolating ball positions...")
            tracks["ball"] = tracker.ball_interpolation(tracks["ball"])

            # Initialize modules
            frame_generator = read_video_frames(input_path)
            first_frame = next(frame_generator)

            print("Initializing Camera Movement detector...")
            camera_movement = CameraMovement(first_frame)

            print("Getting FPS...")
            cap = cv2.VideoCapture(input_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            speed_dist = SpeedAndDistance_Estimator(frame_rate=fps)

            print("Initializing Team Assigner...")
            team_assigner = TeamAssigner()
            team_assigner.assign_team_color(first_frame, tracks["players"][0])

            player_assigner = PlayerBallAssigner()
            team_ball_possession = []

            print("Processing frames...")
            frame_generator = read_video_frames(input_path)

            for frame_num, frame in enumerate(frame_generator):
                camera_movement_per_frame = camera_movement.get_camera_movement([frame], read_from_stub=False)
                camera_movement.adjust_single_frame_tracks(tracks, frame_num, camera_movement_per_frame[0])

                # Team assignment
                players = tracks["players"][frame_num]
                for player_id, p in players.items():
                    team = team_assigner.get_player_team(frame, p["bbox"], player_id)
                    p["team"] = team
                    p["team_color"] = team_assigner.team_colors[team].tolist()

                # Ball assignment
                if 1 in tracks["ball"][frame_num]:
                    ball_bbox = tracks["ball"][frame_num][1]["bbox"]
                    pid = player_assigner.assign_ball_to_player(players, ball_bbox)
                    if pid != -1:
                        players[pid]["ball_possession"] = True
                        team_ball_possession.append(players[pid]["team"])
                    else:
                        team_ball_possession.append(team_ball_possession[-1] if team_ball_possession else 0)
                else:
                    team_ball_possession.append(team_ball_possession[-1] if team_ball_possession else 0)

            # Speed and distance
            speed_dist.add_speed_and_distance(tracks)

            print("Drawing frames...")
            output_frames = []
            frame_generator = read_video_frames(input_path)
            team_pos_np = np.array(team_ball_possession)

            for i, frame in enumerate(frame_generator):
                frame = tracker.draw_annotations([frame], tracks, team_pos_np, i)[0]
                frame = speed_dist.draw_speed_and_distance([frame], tracks, i)[0]
                output_frames.append(frame)

            output_filename = os.path.basename(input_path).split('.')[0] + "_processed.mp4"
            output_path = os.path.join("output", output_filename)

            save_video(output_frames, output_path, fps)

            print("DONE")

            return {
                "processed_video_url": output_filename
            }

        except Exception as e:
            return {"error": str(e)}

        finally:
            gc.collect()
