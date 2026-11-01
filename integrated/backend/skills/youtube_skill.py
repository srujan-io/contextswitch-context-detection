from .base import WebsiteSkill, Action, Parameter

class YouTubeSkill(WebsiteSkill):
    website_id = "youtube"
    name = "YouTube"
    actions = {
        "play_video": Action("Play or resume the current video.", ["video_player"], ["video_player"], gestures=["voice","hand","head"]),
        "pause_video": Action("Pause the current video.", ["video_player"], ["video_player"], gestures=["voice","hand","head"]),
        "seek_forward": Action("Move the video forward.", ["video_player"], ["video_player"], [Parameter("seconds","integer",minimum=1,maximum=300)], ["voice","hand"]),
        "seek_backward": Action("Move the video backward.", ["video_player"], ["video_player"], [Parameter("seconds","integer",minimum=1,maximum=300)], ["voice","hand"]),
        "change_playback_speed": Action("Change video playback speed.", ["video_player"], ["video_player"], [Parameter("speed","number",minimum=0.25,maximum=2.0)], ["voice","hand"]),
        "scroll_page": Action("Scroll the YouTube page.", ["homepage","search_results","playlist","channel_page","shorts","other"], ["page"], [Parameter("direction","string",choices=["up","down"])], ["head","hand"]),
        "search_videos": Action("Search YouTube videos.", ["homepage","search_results","other"], ["search_box"], [Parameter("query","string")], ["voice"], True)
    }
