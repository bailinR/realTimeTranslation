from __future__ import annotations

import audioop


def downmix_to_mono(pcm_bytes: bytes, channels: int) -> bytes:
    if channels <= 1:
        return pcm_bytes
    if channels == 2:
        return audioop.tomono(pcm_bytes, 2, 0.5, 0.5)
    width = 2
    frame_size = width * channels
    mono = bytearray()
    for index in range(0, len(pcm_bytes), frame_size):
        frame = pcm_bytes[index : index + frame_size]
        mono.extend(frame[:2])
    return bytes(mono)


def resample_pcm16(pcm_bytes: bytes, src_rate: int, dst_rate: int, state: tuple | None = None) -> tuple[bytes, tuple | None]:
    if src_rate == dst_rate:
        return pcm_bytes, state
    return audioop.ratecv(pcm_bytes, 2, 1, src_rate, dst_rate, state)
