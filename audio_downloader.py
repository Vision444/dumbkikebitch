"""Main audio downloading functionality."""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import logging

import yt_dlp
import requests
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
from mutagen.mp3 import MP3


class AudioConfig:
    """Configuration for audio downloader."""

    def __init__(self):
        self.output_directory = os.getenv("OUTPUT_DIRECTORY", "./downloads")
        self.audio_quality = os.getenv("AUDIO_QUALITY", "best")
        self.ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
        self.default_artist = os.getenv("DEFAULT_ARTIST", "")
        self.default_album = os.getenv("DEFAULT_ALBUM", "")

    def ensure_output_directory(self):
        """Create output directory if it doesn't exist."""
        Path(self.output_directory).mkdir(parents=True, exist_ok=True)


class AudioMetadata:
    """Audio metadata container."""

    def __init__(
        self,
        artist: str = None,
        title: str = None,
        album: str = None,
        cover_path: str = None,
    ):
        self.artist = artist
        self.title = title
        self.album = album
        self.cover_path = cover_path

    def is_empty(self) -> bool:
        """Check if all metadata fields are empty."""
        return not any([self.artist, self.title, self.album, self.cover_path])

    @classmethod
    def from_youtube_info(cls, info):
        """Create metadata from YouTube video info."""
        return cls(
            artist=info.get("uploader"),
            title=info.get("title"),
            album=info.get("album"),
        )

    @classmethod
    def from_soundcloud_info(cls, info):
        """Create metadata from SoundCloud track info."""
        return cls(
            artist=info.get("uploader", {}).get("username"),
            title=info.get("title"),
            album=None,
        )


class AudioDownloader:
    """Main class for downloading and processing audio."""

    def __init__(self, config: AudioConfig = None, verbose: bool = False):
        self.config = config or AudioConfig()
        self.verbose = verbose
        self.config.ensure_output_directory()
        self.logger = logging.getLogger(__name__)
        # Track last progress percentage to reduce spam
        self._last_progress_pct = -1

    def _yt_progress_hook(self, progress_dict):
        """yt-dlp progress hook for detailed logging without spamming."""
        status = progress_dict.get("status")
        if status == "downloading":
            pct_str = (progress_dict.get("_percent_str") or "").strip()
            eta_str = (progress_dict.get("_eta_str") or "").strip()
            speed_str = (progress_dict.get("_speed_str") or "").strip()

            # Parse numeric percent for throttled logs
            try:
                pct_numeric = int(float(pct_str.replace("%", "") or 0))
            except Exception:
                pct_numeric = -1

            if pct_numeric >= 0 and pct_numeric // 5 != self._last_progress_pct:
                self._last_progress_pct = pct_numeric // 5
                self.logger.debug(
                    f"yt-dlp: downloading... {pct_str} | speed={speed_str or '?'} | eta={eta_str or '?'}"
                )

        elif status == "finished":
            self.logger.info("yt-dlp: download completed, starting post-processing...")
        elif status == "error":
            self.logger.error("yt-dlp: download failed")

    def download(
        self, url: str, metadata: AudioMetadata = None, quality: str = None
    ) -> Path:
        """Download audio from URL and apply metadata."""
        if metadata is None:
            metadata = AudioMetadata()

        quality = quality or self.config.audio_quality

        # Configure yt-dlp options
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": os.path.join(self.config.output_directory, "%(title)s.%(ext)s"),
            "ffmpeg_location": self.config.ffmpeg_path,
            "quiet": not self.verbose,
            "no_warnings": not self.verbose,
            "progress_hooks": [self._yt_progress_hook] if self.verbose else [],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # Get the downloaded file path
                filename = ydl.prepare_filename(info)
                # yt-dlp may have changed the extension to .mp3
                if filename.endswith(".webm") or filename.endswith(".m4a"):
                    filename = Path(filename).with_suffix(".mp3")

                output_file = Path(filename)

                # Apply metadata
                self._apply_metadata(output_file, metadata)

                return output_file

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            raise

    def _apply_metadata(self, file_path: Path, metadata: AudioMetadata):
        """Apply metadata to MP3 file."""
        try:
            audio = MP3(file_path, ID3=ID3)

            # Add ID3 tag if it doesn't exist
            if audio.tags is None:
                audio.add_tags()

            # Apply metadata
            if metadata.title:
                audio.tags.add(TIT2(encoding=3, text=metadata.title))

            if metadata.artist:
                audio.tags.add(TPE1(encoding=3, text=metadata.artist))

            if metadata.album:
                audio.tags.add(TALB(encoding=3, text=metadata.album))

            # Add cover art if provided
            if metadata.cover_path and os.path.exists(metadata.cover_path):
                with open(metadata.cover_path, "rb") as cover_file:
                    cover_data = cover_file.read()
                    audio.tags.add(
                        APIC(
                            encoding=3,
                            mime="image/jpeg",
                            type=3,  # Cover (front)
                            desc="Cover",
                            data=cover_data,
                        )
                    )

            audio.save()
            self.logger.info(f"Metadata applied to {file_path.name}")

        except Exception as e:
            self.logger.warning(f"Failed to apply metadata: {e}")

    def validate_url(self, url: str) -> bool:
        """Validate YouTube/SoundCloud URL."""
        url_lower = url.lower()
        return any(
            pattern in url_lower
            for pattern in ["youtube.com/watch", "youtu.be/", "soundcloud.com"]
        )
