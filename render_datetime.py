#!/usr/bin/env python3
#    The MIT License (MIT)
#    Copyright (c) Kiyo Chinzei (kchinzei@gmail.com)
#    Permission is hereby granted, free of charge, to any person obtaining a copy
#    of this software and associated documentation files (the "Software"), to deal
#    in the Software without restriction, including without limitation the rights
#    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#    copies of the Software, and to permit persons to whom the Software is
#    furnished to do so, subject to the following conditions:
#    The above copyright notice and this permission notice shall be included in
#    all copies or substantial portions of the Software.
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#    THE SOFTWARE.

REQUIRED_PYTHON_VERSION = (3, 9)

'''
Render date and time of the recording to movies with embedded date/timestamp.
You can also provide date/time using '--datetime' option.
Input movies are assumed in DV (digital video) format, but others acceptable.
'''

epilog_text = \
'''
Appling filters and encoders:
`-vf` and `-af` apply a video or audio filter. You can apply more than two filters.
  * Basically same grammer as ffmpeg command line argument.
  * Parameter is a pair of parameter name and its value connected by a '='.
  * Filter name and the first parameter connected by a '='.
    Ex: `scale=w=iw/2:h=ih/2`
  * If the value is omitted, it assumes True.
    Ex: `crop=w=iw/2:excact`
  * ffmpeg accepts omitting parameter names like `scale=iw/2:ih/2`.
    But here you **cannot omit** parameter names.
  * One `-vf` or `-af` argument contains one filter.
  * To appy two or more filters, use multiple `-vf` or `-af` options.
  * Spaces in arguments are removed even escaped by \\.
`--encode` specifies the output encode. It should be supplied only once.
  * Argument needs to be quoted to avoid shell expands it incorrectly.
  * Argument must starts with a space to avoid `-c:v` or `-c:a` confused from `-c`.

Examples:
  -vf yadif=mode=send_frame : deinterlace by yadif filter,  
      `send_frame` keeps original frame rate.
  -vf eq=gamma=1.3 : gamma correction.
  -af afftdn : FFT based noise reduction.
  --encode " -c:v flibx264 -preset fast -c:a ac3" : output in h264 with audio in ac3.
'''

import argparse
import sys
import os
import re
import tempfile
import subprocess
import datetime
import shlex
import ffmpeg # Need ffmpeg-python (not other similar ones)
from exiftool import ExifToolHelper
from typing import Any, Container, Iterable, List, Dict, Optional, Union

DEFAULT_FONTFILE = 'CRR55.TTF'
EXIF_KEY_HINTS = ['CreateDate', 'ModifyDate', 'DateTimeOriginal', 'OffsetTime', 'Aperture', 'Gain', 'Exposure', 'WhiteBalance', 'ISO', 'ImageStabilization', 'FNumber', 'Shutter', 'FrameRate', 'Rotation', 'GPS', 'Make', 'Model', 'MajorBrand', 'MinorVersion', 'CompatibleBrands', 'FileFunctionFlags']

cwd = os.path.dirname(os.path.realpath(__file__))

# Global variable
font_path = os.path.join(cwd, 'font', DEFAULT_FONTFILE)
mediainfo_path = 'mediainfo'
ffmpeg_path = 'ffmpeg'

def get_mediainfo(path: str, field: str) -> str:
    '''
    Run mediainfo to get information of the movie in path.
    '''
    global mediainfo_path
    p = subprocess.run([mediainfo_path, f'--Output={field}', path], check=True, text=True, stdout=subprocess.PIPE)
    return p.stdout.split('\n')[0]

def parse_string_to_dict(input_string: str) -> Dict[str, Union[str,bool]]:
    # Split the input string by whitespace
    pairs = input_string.split()

    # Initialize an empty dictionary
    parsed_dict = {}

    # Iterate over the pairs and split them into key-value pairs
    for i, pair in enumerate(pairs):
        if pair.startswith('-'):
            key = pair[1:]  # Remove the leading '-'
            if i + 1 < len(pairs) and not pairs[i + 1].startswith('-'):
                value = pairs[i + 1]
            else:
                value = True
            parsed_dict[key] = value

    return parsed_dict


def parse_filter_args_to_dict(input_string: str) -> Dict[str, Union[str,bool]]:
    '''
    Parse ffmpeg style filter agruments to a dictionary.
    Ex: 'scale=w=iw/2: h=ih/2' => {'name': 'scale', 'w': 'iw/2', 'h': 'ih/2'}
    Ex: 'crop=w=iw/2: excact' => {'name': 'crop', 'w': 'iw/2', 'exact': True}
    ffmpeg filters accepts omitting parameter names e.g. 'scale=iw/2:ih/2' but here you cannot.
    '''
    parts = input_string.split('=', 1)
    filter_name= parts[0].strip()
    dictionary = {'name': filter_name}
    if len(parts) == 2:
        pairs = parts[1].split(':')
        for pair in pairs:
            pair = pair.strip()  # Remove leading and trailing spaces
            if '=' in pair:
                key, value = pair.split('=')
                key, value = key.strip(), value.strip()
            else:
                key, value = pair.strip(), True
            dictionary[key] = value
    return dictionary


def copy_exifdata(pathfrom: str, pathto:str):
    with ExifToolHelper() as etool:
        data = etool.get_metadata(pathfrom)
        datatocopy = {key:val for key, val in data[0].items() for keypart in EXIF_KEY_HINTS if keypart in key}
        etool.set_tags(pathto, datatocopy)


def render_datetime(input: str,
                    output: str,
                    optext: Optional[str|None] = None,
                    sec_begin: Optional[float] = 1.0,
                    sec_len: Optional[float] = 4.0,
                    show_tc: Optional[bool] = False,
                    show_date: Optional[bool] = True,
                    show_time: Optional[bool] = True,
                    datetime_opt: Optional[str] = '',
                    args_vfilter: Optional[List[str]] = [],
                    args_afilter: Optional[List[str]] = [],
                    args_encode: Optional[str] = '',
                    text_size: Optional[int] = 5,
                    text_color: Optional[str] = 'white',
                    text_vpos: Optional[str] = 'b',
                    yes: Optional[bool] = False,
                    bug: Optional[bool] = False,
                    simulate: Optional[bool] = False,
                    **kwargs: Any):
    '''
    Render date/time to a movie file.
    Internally uses ffmpeg and mediainfo
    '''
    global ffmpeg_path
    global font_path

    # 1) Prepare output file
    #    If it's a dir, put output there with the same name as input
    reel_name = os.path.basename(input)
    if os.path.isdir(output):
        output = os.path.join(output, reel_name)
    if input == output:
        print(f'Output will overwrite input {input}. Stop this.')
        return 1

    # 2) Get information of the input movie
    # General / Recorded date appears like 2005-07-02 09:48:06 in localtime
    datetime_s = get_mediainfo(input, 'General;%Recorded_Date%')
    date_s = hh_s = mm_s = ss_s = None
    m = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d)( (\d\d):(\d\d)(:(\d\d))?)?', datetime_opt)
    if m is not None:
        year_s = m.group(1)
        month_s = m.group(2)
        day_s = m.group(3)
        hh_s = m.group(5)
        mm_s = m.group(6)
        ss_s = m.group(8)
        if hh_s is None:
            hh_s = '12'
        if mm_s is None:
            mm_s = '00'
        if ss_s is None:
            ss_s = '00'
    else:
        m = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)', datetime_s)
        if m is None:
            print(f'Fail to get recorded date from {input} and you did not provide datetime as option.', file=sys.stderr)
            return 1
        year_s = m.group(1)
        month_s = m.group(2)
        day_s = m.group(3)
        hh_s = m.group(4)
        mm_s = m.group(5)
        ss_s = m.group(6)
    if show_time and hh_s is None:
        print('If you want to render time, you must provide it as option', file=sys.stderr)
        return 1
    if ss_s is None:
        show_tc = False

    # Prepare date / time values for drawtext
    # 1) enable to limit rendering period
    kwargs_enable = {}
    if sec_begin < 0:
        sec_begin = 0
    if sec_len < 0:
        kwargs_enable = {'enable': f'gte(t,{sec_begin})'}
    else:
        kwargs_enable = {'enable': f'between(t,{sec_begin},{sec_begin + sec_len})'}

    # Font size / position
    height = int(get_mediainfo(input, 'Video;%Height%'))
    text_size = height * text_size / 100
    if text_vpos == 't':
        ypos = '2*lh'
    else:
        ypos = 'h-(2*lh)'
    kwargs_enable |= {'fontfile': font_path, 'fontsize': text_size, 'fontcolor': text_color, 'borderw': 2} 

    # 2) Text for drawtext
    # Need clock advanced by sec_begin.
    d = datetime.datetime(int(year_s), int(month_s), int(day_s), int(hh_s), int(mm_s), int(ss_s)) + \
        datetime.timedelta(seconds = sec_begin)
    year_s1 = f'{d.year}'
    month_s1 = f'{d.month:02}'
    day_s1 = f'{d.day:02}'
    hh_s1 = f'{d.hour:02}'
    mm_s1 = f'{d.minute:02}'
    kwargs_date = {'text': f'{year_s1}-{month_s1}-{day_s1}' if show_date else ''} | kwargs_enable
    kwargs_time = {'text': f'{hh_s1}:{mm_s1}' if show_time else ''} | kwargs_enable
    if show_time and show_tc:
        rate = float(get_mediainfo(input, 'General;%FrameRate%'))
        kwargs_time |= {'timecode': f'{hh_s}:{mm_s}:{ss_s};00', 'rate': rate, 'tc24hmax': True, 'text': ''}

    # 3) Filters if optionally specified
    # --> move to the ffmpeg parser

    # 4) Special workaround for DV
    # ffmpeg creation_time convert time to UTC. This is fine, but But Sony DV format seems assuming localtime.
    # Need 'Z' to prevent ffmpeg converting local timezone to UTC.
    # cf: https://video.stackexchange.com/questions/25568/what-is-the-correct-format-of-media-creation-time
    # Saving DV requires target. We assume here NTSC.
    datetime_s = f'{year_s}-{month_s}-{day_s} {hh_s}:{mm_s}:{ss_s}'
    root, fileext = os.path.splitext(output)

    if optext is not None:
        if not optext.startswith('.'):
            optext = '.' + optext
        output = root + optext
        fileext = optext

    """
    kwargs_output = {} # {'c:a': 'copy', 'c:v': 'copy'}
    if fileext == '.dv':
        kwargs_output |= {'target': 'ntsc-dv'}
        kwargs_output |= {'metadata': f'creation_time={datetime_s}Z'}
    else:
        kwargs_output |= {'c:v': 'libx264', 'preset': 'fast', 'crf': 23}
        kwargs_output |= {'metadata': f'creation_time={datetime_s}'}
    kwargs_output |= parse_string_to_dict(args_encode) # may override c:v etc.
    """
    kwargs_output = parse_string_to_dict(args_encode)
    if fileext == '.dv':
        kwargs_output |= {'metadata': f'creation_time={datetime_s}Z', 'target': 'ntsc-dv'}
    else:
        kwargs_output |= {'metadata': f'creation_time={datetime_s}'}
    
    # 5) Render output movie
    #    Do it async
    in_mov = ffmpeg.input(input)
    video = in_mov.video
    audio = in_mov['a:0'] # Need to drop two or more audio streams if exist.

    # 6) ffmpeg bug workaround.
    # ffmpeg dv muxer sporadically fails around audio.
    # As workaound, first write it in tmp file as wav.
    # Then read it. Theoretically lossless.
    tmp_wav = None
    if bug:
        arate = get_mediainfo(input, 'Audio;%SamplingRate% ') # a space to split...
        arate = arate.split(' ')[0]
        temp_file = tempfile.mkstemp(suffix='.wav')
        os.close(temp_file[0]) # We don't write from python.
        tmp_wav = temp_file[1]
        _, stderr = (
            ffmpeg
            .output(audio, tmp_wav, **{'f': 's16le', 'ar': arate, 'ac': 2})
            .run(cmd=ffmpeg_path, quiet=True, overwrite_output=yes, capture_stderr=True)
        )
        audio = ffmpeg.input(tmp_wav, **{'f': 's16le', 'ar': arate, 'ac': 2}).audio

    # 7) Build filter chain.
    for argstr in args_vfilter:
        # Apply filters before drawtext
        # ffmpeg.filter() requires a filter name is explicitly given.
        # kwargs_filter = parse_string_to_dict(argstr)
        kwargs_filter = parse_filter_args_to_dict(argstr)
        filter_name = kwargs_filter.pop('name', None)
        if filter_name is not None:
            video = ffmpeg.filter(video, filter_name, **kwargs_filter)
    if show_date:
        video = ffmpeg.drawtext(video, x='w*0.02', y=ypos, **kwargs_date)
    if show_time:
        video = ffmpeg.drawtext(video, x='(w-tw)-(w*0.02)', y=ypos, **kwargs_time)
    for argstr in args_afilter:
        kwargs_filter = parse_filter_args_to_dict(argstr)
        filter_name = kwargs_filter.pop('name', None)
        if filter_name is not None:
            video = ffmpeg.filter(audio, filter_name, **kwargs_filter)
    result_stream = ffmpeg.output(video, audio, output, **kwargs_output)

    # 8) Do it or simulate it.
    retval = 0
    if simulate:
        args = ffmpeg.compile(result_stream, cmd=ffmpeg_path, overwrite_output=yes)
        print(f'{shlex.join(args)}')
    else:
        process = ffmpeg.run_async(result_stream, cmd=ffmpeg_path, quiet=True, overwrite_output=yes, pipe_stderr=True)
        _, stderr = process.communicate()
        if process.returncode == 0:
            copy_exifdata(input, output)
        else:
            print(f' -- stderr: {stderr.decode('utf-8')}', file=sys.stderr)
        retval = process.returncode
    if tmp_wav:
        os.remove(tmp_wav)
    return retval


def main(argv: Optional[List[str]] = None) -> int:
    global ffmpeg_path
    global font_path
    global epilog_text

    if sys.version_info < REQUIRED_PYTHON_VERSION:
        print(f'Requires python {REQUIRED_PYTHON_VERSION} or newer.', file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description='Render date/time to the given movie files',
                                     fromfile_prefix_chars='+',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=epilog_text)

    parser.add_argument('-s', '--size', dest='text_size', metavar='%', type=float, default="5", help='Font size in %%')
    parser.add_argument('-c', '--color', dest='text_color', metavar='str', default="white", help='Text color (yellow, etc)')
    parser.add_argument('-b', '--begin', dest='sec_begin', metavar='sec', type=float, default=1.0, help='Begin rendring date/time, in second')
    parser.add_argument('-l', '--len', dest='sec_len', metavar='sec', type=float, default=4.0, help='Duration of rendring date/time. No end if negative')
    parser.add_argument('-v', '--vpos', dest='text_vpos', metavar='t/b', choices=['t','b'], default="b", help='Render text at top or bottom')
    parser.add_argument('--font', metavar='path', default=None, help='Full path to a font file')
    parser.add_argument('-t', '--tc', dest='show_tc', action='store_true', default=False, help='Render timecode rather than time in HH:MM')
    parser.add_argument('--date', dest='show_date', action=argparse.BooleanOptionalAction, default=True, help='Render date or not')
    parser.add_argument('--time', dest='show_time', action=argparse.BooleanOptionalAction, default=True, help='Render time or not')
    parser.add_argument('--datetime', dest='datetime_opt', metavar='str', default='', help='Use given "yyyy-mm-dd[ HH:MM[:SS]]" as date/time')
    parser.add_argument('--vf', '-vf', dest='args_vfilter', metavar='args', action='append', default=[], help='Video filter. Ex "scale=w=iw/2:h=ih/2"')
    parser.add_argument('--af', '-af', dest='args_afilter', metavar='args', action='append', default=[], help='Audio filter. Ex "afftdn=nr=10:nf=-40"')
    parser.add_argument('--encode', dest='args_encode', metavar='args', default='', help='Encode arguments. Ex " -c:v libx264 -preset slow -c:a ac3"')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='Yes to overwrite')
    parser.add_argument('--ffmpeg', metavar='path', default=None, help='Full path to ffpmeg')
    parser.add_argument('--bug', action='store_true', default=False, help='Bug workaroound. Try it when "Assertion cur_size >= size"')
    parser.add_argument('--simulate', action='store_true', default=False, help='Print generated ffmpeg command, no execution')
    parser.add_argument('-e', '--ext', dest='optext', metavar='ext', default=None, help='File extension for output (dv, mov, mp4 etc)')
    parser.add_argument('infiles', nargs='+', type=str, help='Input movie files')
    parser.add_argument('output', help='Output dir or file')

    args = parser.parse_args(args=argv)
    args.arg0 = ' '.join(argparse._sys.argv)

    if args.font is not None:
        font_path = args.font
    if args.ffmpeg is not None:
        ffmpeg_path = args.ffmpeg
    for path in args.infiles:
        args.input = path
        render_datetime(**vars(args))
    return 0

if __name__ == '__main__':
    sys.exit(main())
