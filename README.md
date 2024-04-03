# DV Archive Workflow

CLI Tools and workflow to organize DV (digital video) for achiving

This is a personal project to digitized old video tapes then organize them using recording date and time.
The most of credit should go Léo Bernard in concept, tools and workflow.
See Léo's Blog ["Capturing and Archiving MiniDV Tapes on macOS"](https://leolabs.org/blog/capture-minidv-on-macos/).
My contribution is in two python scripts.

## Concept
As Léo pointed out, I also care about
- Lossless capture and archiving,
- Split clips by timestamp, and
- Maintain embedded timestamp.

In addition to these, I also care about
- Workflow to share videos with my family.
- VHS tapes can also be archhived in the same way.

## Tools

To share videos with my family, I made two python scripts
- `render_datetime.py` - `ffmpeg` wrapper to render date and/or time in the first few seconds of the video clips.
Date/time are usually automatically obtained from embedded timestamp.
For VHS, it can be manually given.
- `mv_datetime.py` - rename (`mv`) video file name to date_time format.
For example, if a DV file starts at 12:30:45 of Apr. 1, 2024, its file name will be 2024-04-01_1230_45.dv

See usage, possible option at the botom of this readme.
The rest of tools (hardware and software, installation) are same as [Léo did](https://leolabs.org/blog/capture-minidv-on-macos/).

## Workflow

Léo explained first four steps.
1. Connect a video player to Mac using a FireWire cable and dongles.
1. Find the device descriptions using `ffmpeg`.
1. Capture video using `ffmpeg-dl`.
1. Split video clips using `dvpackager`.
1. Rename the video clips files to date/time using `mv_datetime.py`.
1. Archive these video clips. I store video clips from one tape in a folder.

### To share videos with others

I do the following to share archived videos with others.
1. Render date/time using `render_datetime.py`.
1. Re-connect video clips using `cat` if you feel necessary.
Ex: `cat foo1.dv foo2.dv foo3.dv > foo.dv`  
This is another great side of handling video clips in `.dv` format.
1. Convert video clips to `.mp4` using `ffmpeg`.

'Raw' archived videos are not suitablle for sharing with others because,
- `.dv` is not a popular format. They want `.mp4` for example,
- Reading timestamp is not available in popular apps, and
- `dvpackager` can produce too many small video clips.

#### To archive VHS

If you have a DV+VHS deck like Sony WV-DR7, you can also capture from VHS tapes using `ffmpeg-dl`.
But VHS tapes do not store timestamps.
This means certain limitations:
- You cannot automatically split them using `dvpackager`.
- You cannot automatically rename them by date/time.

If you luckily know date of recording (e.g., it's rendered in video),
you can manually provide date (optionally time also) to `mv_datetime.py` and `render_datetime.py`.

## Usage

```bash
mv_datetime.py [-h] [--format str] [--datetime str] [-y] infiles [infiles ...]
```

Rename (mv) movie files using 'Recoeded Date' field.

| Options |     |
| ------- | --- |
| `-h, --help`      | show this help message and exit |
| `--format str`    | Custom format string, default=`"{}-{}-{}_{}{}_{}"` |
| `--datetime str`  | Use given `"yyyy-mm-dd[ HH:MM[:SS]]"` as date/time |
| `-y, --yes`       | Yes to overwrite |

```bash
render_datetime.py [-h] [options] [--datetime str] infiles [infiles ...] output
```

Render date/time to the given movie files.

| Options |     |
| ------- | --- |
| `-h, --help`           | show this help message and exit |
| `-s %, --size %`       | Font size in % |
| `-c str, --color str`  | Text color (yellow, etc) |
| `-b sec, --begin sec`  | Begin rendring date/time, in second |
| `-l sec, --len sec`    | Duration of rendring date/time. No end if negative |
| `-v t/b, --vpos t/b`   | Render text at top or bottom |
| `--font path`          | Full path to a font file |
| `-t, --tc `            | Render timecode rather than HH:MM |
| `--date, --no-date`    | Render date |
| `--time, --no-time`    | Render time |
| `--datetime str`       | Use given `"yyyy-mm-dd[ HH:MM[:SS]]"` as date/time |
| `--filter args`        | Optional filter arguments. Ex `" -vf estdif -interp 6p"` |
| `--encode args`        | Optional encode arguments. Ex `" -c:v libx264 -preset slow -crf 22 -c:a copy"` |
| `-y, --yes`            | Yes to overwrite. |

`--filter` and `--encode` are intended to apply a video filter, typically a de-interlace and output encoder parameters.
To escape filter / encoder options being parsed as switches for `render_datetime.py`, surround them by quotations, and insert a space before first parameter.
Parameters start with `-` are parsed as switches for the filter and the encoder.
Space is used to separate option switch and value(s).

Video filers are not limited to de-interlace.
For video filters, see [Video Filters](https://ffmpeg.org/ffmpeg-filters.html#Video-Filters) of `ffmpeg` document.
For encoders, see [Encoders](https://ffmpeg.org/ffmpeg-codecs.html#Encoders) of `ffmpeg` document.

#### Preriquisite

Follow [Léo did](https://leolabs.org/blog/capture-minidv-on-macos/).
