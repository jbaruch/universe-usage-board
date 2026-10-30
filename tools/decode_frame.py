"""Decode the badge's 320x240 little-endian RGB565 framebuffer to PNG (Pillow)."""
import argparse
from pathlib import Path


def main():
    from PIL import Image
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    if len(raw) != 320 * 240 * 2:
        parser.error('Expected a 153600-byte 320x240 RGB565 frame.')
    rgb = bytearray()
    for offset in range(0, len(raw), 2):
        pixel = raw[offset] | raw[offset + 1] << 8
        rgb.extend((((pixel >> 11) & 31) * 255 // 31,
                    ((pixel >> 5) & 63) * 255 // 63, (pixel & 31) * 255 // 31))
    Image.frombytes('RGB', (320, 240), bytes(rgb)).save(args.output)


if __name__ == '__main__':
    main()
