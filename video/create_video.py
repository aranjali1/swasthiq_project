"""Build the three-minute failure analysis video on macOS.

Requires Pillow, imageio-ffmpeg, and the built-in `say` command.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
PUBLIC.mkdir(exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SECTIONS = [
    (
        "A booking request with two dates",
        "The agent usually handles the supplied scripts, but I wanted to see what happens when a caller gives conflicting dates in one sentence. This video walks through a real local run, what the agent did, and why the result is unsafe. The test date is October first, twenty twenty-six.",
        ["TEST SETUP", "Today: 1 October 2026", "Caller wants Dr. Rao", "Two date phrases in one utterance"],
        "01 / THE QUESTION",
    ),
    (
        "The caller says: kal, 3 tareekh",
        "Here is the input. The caller says kal, meaning tomorrow, and also three tareekh, meaning the third of the month. On October first, tomorrow is October second. The third is October third. Those cannot both describe the same appointment date. At this point the agent should ask a question before it touches a booking tool.",
        ["INPUT", "Dr. Rao ke saath kal, 3 tareekh ko", "appointment chahiye.", "Harpreet Singh, 9812200311."],
        "02 / THE CONTRADICTION",
    ),
    (
        "It booked the third anyway",
        "I ran show failure dot py against the agent. The terminal state is booked. The reply says the appointment is on October third at nine in the morning with Dr. Anjali Rao. That is a concrete mistake. The caller might have meant tomorrow, October second. A successful tool call does not mean the agent understood the instruction.",
        ["ACTUAL RESULT", "terminal_state: booked", "date: 2026-10-03", "time: 09:00"],
        "03 / OBSERVED RESULT",
    ),
    (
        "The parser silently picks the last date",
        "The cause is in the date extraction rule. It collects date mentions, sorts them by their position in the sentence, and takes the last one. That rule is useful for a clear correction, such as, not Friday, Saturday. Here there is no correction. The two phrases conflict, but the parser treats the later phrase as the winner.",
        ["ROOT CAUSE", "date mentions -> sort by position", "last mention -> 3 October", "no conflict check before booking"],
        "04 / WHY IT HAPPENED",
    ),
    (
        "Tool checks cannot resolve meaning",
        "The booking tool does recheck whether the selected slot is available, and the shared tool context prevents two simultaneous bookings of that slot. Those checks protect the clinic data. They cannot tell which date the caller intended. The error happens earlier, when the conversation is translated into a single date. This is why a valid booking can still be the wrong outcome.",
        ["WHAT THE TOOLS CHECK", "Slot exists and is available", "Duplicate booking is blocked", "Caller intent is not verified"],
        "05 / THE BOUNDARY",
    ),
    (
        "The fix is to pause and clarify",
        "I would keep all distinct dates found in the latest request. If they disagree and there is no explicit correction, the agent should ask which date the caller means, or hand off if clarification is unavailable. Then I would add this exact sentence as a regression test that forbids booking. The supplied fifteen scripts and eight adversarial scripts pass locally across three runs, but they did not cover this conflict. That is the lesson from this failure.",
        ["FIX AND REGRESSION", "Detect conflicting dates", "Ask before any booking tool call", "Add a test that forbids booking"],
        "06 / NEXT CHANGE",
    ),
]


def font(size: int, bold: bool = False):
    name = "Avenir Next.ttc" if bold else "Avenir.ttc"
    return ImageFont.truetype(f"/System/Library/Fonts/{name}", size)


def make_slide(index: int, section: tuple, output: Path):
    title, _, lines, eyebrow = section
    im = Image.new("RGB", (1280, 720), "#091721")
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1280, 14), fill="#31d2b2")
    draw.rounded_rectangle((42, 44, 1238, 676), radius=28, fill="#10242d", outline="#25424b", width=2)
    draw.text((82, 84), "SWASTHIQ / FAILURE ANALYSIS", font=font(21, True), fill="#31d2b2")
    draw.text((82, 152), title, font=font(47, True), fill="#f4f5f1")
    draw.text((82, 242), eyebrow, font=font(23, True), fill="#97b4b8")
    draw.rounded_rectangle((78, 296, 1200, 580), radius=18, fill="#172f39")
    for i, line in enumerate(lines):
        color = "#31d2b2" if i == 0 else "#f4f5f1"
        draw.text((112, 325 + i * 57), line, font=font(29 if i else 24, i == 0), fill=color)
    draw.text((82, 620), f"{index + 1:02d} / 06", font=font(20, True), fill="#97b4b8")
    draw.rectangle((265, 632, 1190, 637), fill="#2d4a52")
    draw.rectangle((265, 632, 265 + int(925 * (index + 1) / 6), 637), fill="#31d2b2")
    im.save(output)


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    with tempfile.TemporaryDirectory(prefix="swasthiq-video-") as temp:
        work = Path(temp)
        slide_list, audio_list = [], []
        captions = ["WEBVTT", ""]
        for index, section in enumerate(SECTIONS):
            slide = work / f"slide{index}.png"
            aiff = work / f"voice{index}.aiff"
            wav = work / f"segment{index}.wav"
            make_slide(index, section, slide)
            pace = (110, 120, 120, 120, 130, 145)[index]
            run("say", "-v", "Aman", "-r", str(pace), "-o", str(aiff), section[1])
            info = subprocess.run(("afinfo", str(aiff)), check=True, capture_output=True, text=True).stdout
            duration = float(re.search(r"estimated duration: ([\d.]+) sec", info).group(1))
            if duration > 29.5:
                raise RuntimeError(f"Narration {index + 1} is {duration:.1f}s and would be cut off")
            print(f"Section {index + 1}: {duration:.1f}s of narration")
            sentences = re.split(r"(?<=[.!?])\s+", section[1])
            words = sum(len(sentence.split()) for sentence in sentences)
            elapsed = 0.0
            for sentence in sentences:
                next_elapsed = elapsed + duration * len(sentence.split()) / words
                start, end = index * 30 + elapsed, index * 30 + next_elapsed
                stamp = lambda t: f"{int(t // 3600):02d}:{int(t // 60) % 60:02d}:{int(t) % 60:02d}.{int(t % 1 * 1000):03d}"
                captions.extend((f"{stamp(start)} --> {stamp(end)}", sentence, ""))
                elapsed = next_elapsed
            run(FFMPEG, "-y", "-i", str(aiff), "-af", "apad", "-t", "30", "-ar", "44100", "-ac", "2", str(wav))
            slide_list.append(f"file '{slide}'\nduration 30\n")
            audio_list.append(f"file '{wav}'\n")
        # The last frame needs its own entry for the concat demuxer to hold it.
        (work / "slides.txt").write_text("".join(slide_list) + f"file '{work / 'slide5.png'}'\n")
        (work / "audio.txt").write_text("".join(audio_list))
        run(FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(work / "audio.txt"),
            "-c:a", "pcm_s16le", str(work / "audio.wav"))
        output = PUBLIC / "failure-analysis.mp4"
        run(FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(work / "slides.txt"),
            "-i", str(work / "audio.wav"), "-t", "180", "-r", "24", "-c:v", "libx264",
            "-preset", "medium", "-crf", "25", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:a", "128k", "-movflags", "+faststart", str(output))
        (PUBLIC / "failure-analysis.vtt").write_text("\n".join(captions))
        print(output)
        print(output.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
