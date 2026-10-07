"""Renders the example's story videos: a Presto promo and two food videos.

Frames are drawn with Pillow and piped to ffmpeg. Output follows the
stories_player media rules: H.264 Main, yuv420p, faststart MP4, AAC audio,
9:16. Each video also gets a poster that is exactly its first frame, and the
promo gets a 480p low-quality rendition.
"""
import math
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SCRATCH = sys.argv[1]
OUT = sys.argv[2]  # example/assets/videos
IMAGES = sys.argv[3]  # example/assets/images
MUSIC = sys.argv[4]  # example/assets/audio/sunny_loop.wav
W, H, FPS = 720, 1280, 30

BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
UNICODE = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
ORANGE_A = (255, 87, 34)
ORANGE_B = (255, 140, 0)


def font(path, size):
    return ImageFont.truetype(path, size)


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def clamp01(t):
    return max(0.0, min(1.0, t))


def gradient(w, h, a, b):
    base = Image.new("RGB", (w, h), a)
    top = Image.new("RGB", (w, h), b)
    mask = Image.linear_gradient("L").resize((w, h))
    return Image.composite(top, base, mask)


ORANGE_BG = gradient(W, H, ORANGE_A, ORANGE_B)


def cover(img, w, h, zoom=1.0, pan=(0.5, 0.5)):
    """Crops [img] to fill w x h, zoomed in by [zoom], centred on [pan]."""
    scale = max(w / img.width, h / img.height) * zoom
    rw, rh = int(img.width * scale), int(img.height * scale)
    resized = img.resize((rw, rh), Image.LANCZOS)
    x = int((rw - w) * pan[0])
    y = int((rh - h) * pan[1])
    return resized.crop((x, y, x + w, y + h))


def text_center(draw, y, text, fnt, fill, shadow=True):
    box = draw.textbbox((0, 0), text, font=fnt)
    x = (W - (box[2] - box[0])) // 2
    if shadow:
        draw.text((x + 2, y + 3), text, font=fnt, fill=(0, 0, 0, 90))
    draw.text((x, y), text, font=fnt, fill=fill)


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, img.width, img.height), radius=radius, fill=255
    )
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def caption_band(frame, text, t_in, t, sub=None):
    """A caption on a dark pill near the top, sliding down and fading in.

    Near the top, so it never collides with the player's own caption at the
    bottom of the screen.
    """
    k = clamp01((t - t_in) / 0.45)
    if k <= 0:
        return frame
    e = ease_in_out(k)
    title_f, sub_f = font(BLACK, 46), font(BOLD, 28)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tw = probe.textbbox((0, 0), text, font=title_f)[2]
    sw = probe.textbbox((0, 0), sub, font=sub_f)[2] if sub else 0
    pw, ph = max(tw, sw) + 72, 132 if sub else 92
    x0, y0 = (W - pw) // 2, 190 - int((1 - e) * 30)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), radius=30,
                        fill=(0, 0, 0, int(150 * k)))
    d.text(((W - tw) // 2, y0 + 18), text, font=title_f,
           fill=(255, 255, 255, int(255 * k)))
    if sub:
        d.text(((W - sw) // 2, y0 + 80), sub, font=sub_f,
               fill=(255, 214, 170, int(255 * k)))
    return Image.alpha_composite(frame.convert("RGBA"), layer).convert("RGB")


def encode(name, frames, seconds, audio=True, size=(W, H)):
    path = f"{OUT}/{name}.mp4"
    args = [
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-",
    ]
    if audio:
        args += ["-stream_loop", "-1", "-i", MUSIC]
    vf = f"scale={size[0]}:{size[1]}:flags=lanczos,format=yuv420p"
    args += [
        "-vf", vf, "-c:v", "libx264", "-profile:v", "main",
        "-preset", "slow", "-crf", "27" if size[0] >= 720 else "29",
        "-g", str(FPS), "-movflags", "+faststart", "-t", f"{seconds}",
    ]
    if audio:
        args += [
            "-c:a", "aac", "-b:a", "96k", "-ac", "2",
            "-af", f"afade=t=out:st={seconds - 0.8}:d=0.8",
        ]
    else:
        args += ["-an"]
    args.append(path)
    proc = subprocess.Popen(args, stdin=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit(f"ffmpeg failed for {name}")
    return path


def render(frame_fn, seconds):
    return [frame_fn(i / FPS) for i in range(int(seconds * FPS))]


# --------------------------------------------------------------- Presto promo

def presto_promo():
    logo = Image.open(f"{SCRATCH}/presto/hi_0.png").convert("RGB")
    logo = rounded(logo.resize((260, 260), Image.LANCZOS), 58)
    screens = [
        Image.open(f"{SCRATCH}/presto/hi_{i}.png").convert("RGB")
        for i in (2, 3, 5, 8)
    ]
    intro, per, fade, outro = 2.2, 1.9, 0.35, 2.4
    seconds = intro + per * len(screens) + outro

    def logo_card(t, start, title, subtitle, button):
        img = ORANGE_BG.copy().convert("RGBA")
        rings = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rings)
        for r, a in ((430, 22), (340, 30), (250, 38)):
            rr = int(r * (1 + 0.03 * math.sin((t - start) * 3 + r)))
            rd.ellipse((W // 2 - rr, 470 - rr, W // 2 + rr, 470 + rr),
                       fill=(255, 255, 255, a))
        img = Image.alpha_composite(img, rings)
        k = clamp01((t - start) / 0.6)
        s = max(0.01, ease_out_back(k)) if k < 1 else 1.0
        size = max(1, int(260 * s))
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (W // 2 - size // 2 + 6, 470 - size // 2 + 14,
             W // 2 + size // 2 + 6, 470 + size // 2 + 14),
            radius=int(58 * s), fill=(120, 30, 0, 70))
        img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(14)))
        lg = logo.resize((size, size), Image.LANCZOS)
        img.alpha_composite(lg, (W // 2 - size // 2, 470 - size // 2))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        k2 = clamp01((t - start - 0.35) / 0.5)
        if k2 > 0:
            dy = int((1 - ease_in_out(k2)) * 30)
            a = int(255 * k2)
            text_center(d, 660 + dy, title, font(BLACK, 92), (255, 255, 255, a), shadow=False)
            text_center(d, 784 + dy, subtitle, font(UNICODE, 36), (255, 240, 228, a), shadow=False)
        k3 = clamp01((t - start - 0.7) / 0.5)
        if k3 > 0 and button:
            bw, bh = 470, 96
            pulse = 1 + (0.035 * math.sin((t - start) * 5) if k3 >= 1 else 0)
            bw2, bh2 = int(bw * pulse), int(bh * pulse)
            x0, y0 = (W - bw2) // 2, 900 + int((1 - k3) * 30)
            d.rounded_rectangle((x0, y0, x0 + bw2, y0 + bh2), radius=bh2 // 2,
                                fill=(255, 255, 255, int(255 * k3)))
            f = font(BLACK, 36)
            box = d.textbbox((0, 0), button, font=f)
            d.text((x0 + (bw2 - box[2]) // 2, y0 + (bh2 - box[3]) // 2 - 4),
                   button, font=f, fill=ORANGE_A + (int(255 * k3),))
        return Image.alpha_composite(img, layer).convert("RGB")

    def screen_at(i, t_local):
        zoom = 1.0 + 0.07 * ease_in_out(t_local / (per + fade))
        return cover(screens[i], W, H, zoom=zoom, pan=(0.5, 0.35))

    def frame(t):
        if t < intro:
            return logo_card(t, 0.0, "Presto", "1M+ downloads  •  ★ 4.4", None)
        t2 = t - intro
        n = len(screens)
        if t2 < per * n:
            i = int(t2 // per)
            local = t2 - i * per
            img = screen_at(i, local)
            if i == 0 and local < fade:
                prev = logo_card(intro, 0.0, "Presto", "1M+ downloads  •  ★ 4.4", None)
                img = Image.blend(prev, img, ease_in_out(local / fade))
            elif i > 0 and local < fade:
                prev = screen_at(i - 1, per + local)
                img = Image.blend(prev, img, ease_in_out(local / fade))
            return img
        t3 = t2 - per * n
        card = logo_card(t3 + 0.0, 0.0, "Presto", "Food & groceries, delivered", "Download Presto")
        if t3 < fade:
            prev = screen_at(n - 1, per + t3)
            card = Image.blend(prev, card, ease_in_out(t3 / fade))
        return card

    frames = render(frame, seconds)
    frames[0].save(f"{OUT}/presto_promo_poster.jpg", quality=86)
    encode("presto_promo", frames, seconds)
    encode("presto_promo_480", frames, seconds, size=(480, 854))
    return seconds


# ----------------------------------------------------------------- food videos

def food_video(name, photos, captions, seconds_each=2.6, music=True):
    imgs = [Image.open(f"{IMAGES}/p{p}.jpg").convert("RGB") for p in photos]
    fade = 0.4
    seconds = seconds_each * len(imgs)
    pans = [((0.3, 0.2), (0.6, 0.6)), ((0.6, 0.5), (0.4, 0.3)), ((0.5, 0.2), (0.5, 0.7))]

    def shot(i, t_local):
        k = clamp01(t_local / (seconds_each + fade))
        (sx, sy), (ex, ey) = pans[i % len(pans)]
        pan = (sx + (ex - sx) * k, sy + (ey - sy) * k)
        zoom = 1.12 + 0.12 * ease_in_out(k)
        img = cover(imgs[i], W, H, zoom=zoom, pan=pan)
        return caption_band(img, captions[i][0], 0.35, t_local, captions[i][1])

    def frame(t):
        i = min(int(t // seconds_each), len(imgs) - 1)
        local = t - i * seconds_each
        img = shot(i, local)
        if i > 0 and local < fade:
            prev = shot(i - 1, seconds_each + local)
            img = Image.blend(prev, img, ease_in_out(local / fade))
        return img

    frames = render(frame, seconds)
    frames[0].save(f"{OUT}/{name}_poster.jpg", quality=86)
    encode(name, frames, seconds, audio=music)
    return seconds


if __name__ == "__main__":
    import os
    os.makedirs(OUT, exist_ok=True)
    print("presto_promo", presto_promo())
    print("market_fruit", food_video(
        "market_fruit",
        [1080, 429, 674],
        [("Strawberry season", "2 boxes for the price of 1"),
         ("Picked this morning", "Raspberries, sweet and fresh"),
         ("Delivered cold", "Black grapes in 30 minutes")],
    ))
    print("bakery_sweets", food_video(
        "bakery_sweets",
        [999, 835, 312],
        [("Baked today", "Chocolate pear cake"),
         ("Still warm", "Fresh cookies every hour"),
         ("Pure local honey", "From farm to your door")],
        music=False,
    ))
