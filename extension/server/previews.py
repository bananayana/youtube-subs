import os
import uuid

import boto3
from botocore.client import Config
import ffmpy
import subprocess
import youtube_dl

from django.conf import settings


class VideoPreviewCreator:

    def __init__(self):
        self.s3 = boto3.resource(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_KEY,
            config=Config(signature_version='s3v4')
        )

    def create(self, video_id):
        """
        Fetches preview and saves it to S3
        :param video_id: id of video to fetch
        :return: string: url of preview
        """
        data = self.fetch(video_id)
        name = self.generate_name()
        return self.save(data, name)

    def _cut(self, url, start, duration=5):
        """
        Extract video snippet and encode it to webm
        :param url: url of video to fetch
        :param preview_start: time of snippet start
        :param preview_duration: length of snippet
        :return: string: encoded bytes
        """
        try:
            # TODO: find best encoding props
            ff = ffmpy.FFmpeg(
                inputs={url: '-ss {start}'.format(start=start)},
                outputs={
                    'pipe:1': (
                        '-t {duration} '  # duration of cutted snippet
                        '-codec:v libvpx '  # video codec
                        '-quality realtime -cpu-used 0 '  # processing options
                        # '--threads 4 ' # Number of threads - set to the number of CPU cores
                        # '-b:v 500k ' # desired output video bitrate
                        # '-qmin 10 -qmax 42 ' # quantization levels (0-63) - lower better
                        # '-maxrate 500k '
                        # '-bufsize 1M ' # twice as max rate to have buffer for 2 seconds
                        '-vf scale=-1:480 '  # new video size (-1 means save proportions)
                        # '-codec:a libvorbis -b:a 128k ' # audio codec
                        '-f webm '  # used to specify encoding from pipe
                            .format(duration=duration)
                    )
                }
            )
            f, err = ff.run(stdout=subprocess.PIPE)
        except ffmpy.FFRuntimeError as e:
            # TODO: handle
            raise e
        return f

    def fetch(self, video_id):
        """
        Handle preparation and fetch preview
        :param video_id: id of video to fetch
        :return: string: snippet bytes
        """
        url, duration = self._get_info(video_id)
        return self._cut(url, *self._get_preview_time(duration))

    def generate_name(self):
        """
        Generate unique enough name for snippet
        :return: string: filename
        """
        return uuid.uuid4().hex + '.webm'

    def _get_info(self, video_id):
        """
        Fetch video data from Youtube
        :param video_id: id of video
        :return: tuple: video url, video duration
        """
        url = settings.YOUTUBE_VIDEO_URL.format(video_id=video_id)
        with youtube_dl.YoutubeDL(settings.PREVIEW_PROCESSING_OPTIONS) as ydl:
            res = ydl.extract_info(url, download=False)
        return res['url'], res['duration']

    def _get_preview_time(self, duration):
        """
        Computes the start and duration of snippet
        :param duration: whole video length
        :return: tuple: start, duration
        """
        # TODO: check the logic of snippet length gen
        preview_start = settings.DEFAULT_PREVIEW_START if duration > 2 * settings.DEFAULT_DURATION_REQUIREMENT \
            else duration // 4
        preview_duration = settings.DEFAULT_PREVIEW_DURATION if duration > settings.DEFAULT_DURATION_REQUIREMENT \
            else duration // 2
        return preview_start, preview_duration

    def save(self, data, name):
        """
        Saves snippet data to S3
        :param filename: name of file to save
        :param preview: snippet data
        :return: string: url of snippet
        """
        # TODO: catch errors
        filepath = os.path.join(settings.S3_PREVIEWS_FOLDER, name)
        self.s3.Object(settings.S3_BUCKET_NAME, filepath).put(Body=data, ACL='public-read')
        return os.path.join(settings.S3_BASE_URL, settings.S3_BUCKET_NAME, filepath)


Previewer = VideoPreviewCreator()
