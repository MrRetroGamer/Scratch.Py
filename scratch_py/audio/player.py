"""Sound playback through pygame's mixer, with lazy loading of sb3 assets."""

from __future__ import annotations

import io

import pygame


class AudioPlayer:
    def __init__(self, assets: dict[str, bytes]):
        self.assets = assets
        self.initialized = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.channels: list[pygame.mixer.Channel] = []
        self._warned: set[str] = set()

    def ensure_init(self):
        if self.initialized:
            return
        if not pygame.mixer.get_init():
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
        pygame.mixer.set_num_channels(48)
        for i in range(40):
            try:
                self.channels.append(pygame.mixer.Channel(i))
            except (IndexError, pygame.error):
                break
        self.initialized = True

    def sound_for(self, md5ext: str) -> pygame.mixer.Sound | None:
        self.ensure_init()
        if md5ext in self.sounds:
            return self.sounds[md5ext]
        data = self.assets.get(md5ext)
        if data is None:
            self._warn(f"missing asset {md5ext}")
            return None
        try:
            sound = pygame.mixer.Sound(file=io.BytesIO(data))
        except (pygame.error, ValueError) as exc:
            self._warn(f"cannot decode {md5ext}: {exc}")
            self.sounds[md5ext] = None
            return None
        self.sounds[md5ext] = sound
        return sound

    def play(self, target, sound_index: int):
        sounds = target.data.sounds
        if not 0 <= sound_index < len(sounds):
            return None
        sound = self.sound_for(sounds[sound_index].md5ext)
        if sound is None:
            return None
        channel = self._free_channel()
        if channel is None:
            return None
        channel.set_volume(max(0.0, min(1.0, target.volume / 100.0)))
        try:
            channel.play(sound)
        except pygame.error as exc:
            self._warn(f"play failed: {exc}")
            return None
        return channel

    def play_buffer(self, mono_samples, volume: float = 1.0):
        import numpy

        from ..extensions.music import to_sound_array

        self.ensure_init()
        data = numpy.asarray(mono_samples, dtype=numpy.float32)
        stereo = to_sound_array(data)
        try:
            sound = pygame.mixer.Sound(array=stereo)
        except (ValueError, pygame.error) as exc:
            self._warn(f"buffer play failed: {exc}")
            return None
        channel = self._free_channel()
        if channel is None:
            return None
        channel.set_volume(max(0.0, min(1.0, volume)))
        channel.play(sound)
        return channel

    def is_playing(self, handle) -> bool:
        return bool(handle and handle.get_busy())

    def stop_all(self):
        if not self.initialized:
            return
        for channel in self.channels:
            try:
                channel.stop()
            except pygame.error:
                pass

    def _free_channel(self) -> pygame.mixer.Channel | None:
        for channel in self.channels:
            if not channel.get_busy():
                return channel
        return pygame.mixer.find_channel(force=True)

    def _warn(self, message: str):
        key = message.split(":")[0]
        if key in self._warned:
            return
        self._warned.add(key)
        print(f"[scratch.py audio] {message}")
