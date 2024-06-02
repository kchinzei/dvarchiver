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
Applying filters and encoders:
`-vf` and `-af` apply video and audio filters. You can apply more than two filters.
  * Basically same grammar as ffmpeg command line argument.
  * Parameter is a pair of parameter name and its value connected by a '='.
  * Filter name and the first parameter connected by a '='.
    Ex: `scale=w=iw/2:h=ih/2`
  * If the value is omitted, it assumes True.
    Ex: `crop=w=iw/2:exact`
  * ffmpeg accepts omitting parameter names like `scale=iw/2:ih/2`.
    But here you **cannot omit** parameter names.
  * One `-vf` or `-af` argument contains one filter.
  * To apply two or more filters, use multiple `-vf` or `-af` options.
  * Spaces in arguments are removed even escaped by \\.

`--encode` specifies the output encoder. It should be supplied only once.
  * Argument needs to be quoted to avoid shell unwantedly expands it.
  * Argument must start with a space to avoid `-c:v` or `-c:a` confused from `-c`.

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
import tempfile
from datetime import datetime, timedelta
import shlex
import ffmpeg # Need ffmpeg-python (not other similar ones)
from _util import get_mediainfo, copy_exifdata, append_exifcomment, get_datetime_fromstr, get_datetime_fromfile, guess_offset, datetime2strs
from typing import Any, Container, Iterable, List, Dict, Optional, Union

DEFAULT_FONTFILE = 'CRR55.TTF'

cwd = os.path.dirname(os.path.realpath(__file__))

# Global variable
font_path = os.path.join(cwd, 'font', DEFAULT_FONTFILE)
ffmpeg_path = 'ffmpeg'


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
    Parse ffmpeg style filter arguments to a dictionary.
    Ex: 'scale=w=iw/2: h=ih/2' => {'name': 'scale', 'w': 'iw/2', 'h': 'ih/2'}
    Ex: 'crop=w=iw/2: exact' => {'name': 'crop', 'w': 'iw/2', 'exact': True}
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


def render_datetime(input: str,
                    output: str,
                    optext: Optional[str|None] = None,
                    sec_begin: Optional[float] = 1.0,
                    sec_len: Optional[float] = 4.0,
                    offset: Optional[str|None] = None,
                    guess: Optional[bool] = False,
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
                    arg0: Optional[str] = '',
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
    dt = get_datetime_fromstr(datetime_opt)
    if dt is None:
        dt = get_datetime_fromfile(input, offset)
    if dt is None:
        print(f'Fail to get recorded date from {input} and you did not provide datetime as option.', file=sys.stderr)
        return 1
    if guess:
        dif = guess_offset(input)
        dt += dif
    y0, m0, d0, hh0, mm0, ss0 = datetime2strs(dt)

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
    y1, m1, d1, hh1, mm1, ss1 = datetime2strs(dt + timedelta(seconds = sec_begin))
    kwargs_date = {'text': f'{y1}-{m1}-{d1}' if show_date else ''} | kwargs_enable
    kwargs_time = {'text': f'{hh1}:{mm1}' if show_time else ''} | kwargs_enable
    if show_time and show_tc:
        rate = float(get_mediainfo(input, 'General;%FrameRate%'))
        kwargs_time |= {'timecode': f'{hh0}:{mm0}:{ss0};00', 'rate': rate, 'tc24hmax': True, 'text': ''}

    # 3) Filters if optionally specified
    # --> move to the ffmpeg parser

    # 4) Special workaround for DV
    # ffmpeg creation_time convert time to UTC. This is fine, but But Sony DV format seems assuming localtime.
    # Need 'Z' to prevent ffmpeg converting local timezone to UTC.
    # cf: https://video.stackexchange.com/questions/25568/what-is-the-correct-format-of-media-creation-time
    # Saving DV requires target. We assume here NTSC.
    datetime_s = f'{y0}-{m0}-{d0} {hh0}:{mm0}:{ss0}'
    root, fileext = os.path.splitext(output)

    if optext is not None:
        if not optext.startswith('.'):
            optext = '.' + optext
        output = root + optext
        fileext = optext

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
    # As workaround, first write it in tmp file as wav.
    # Then read it. Theoretically lossless.
    tmp_wav = None
    if bug:
        #arate = get_mediainfo(input, 'Audio;%SamplingRate% ') # a space to split...
        #arate = arate.split(' ')[0]
        arate = 48000 # Resample outside the dv muxer seems necessary since ffmpeg 7.
        temp_file = tempfile.mkstemp(suffix='.wav')
        os.close(temp_file[0]) # We don't write from python.
        tmp_wav = temp_file[1]
        _, stderr = (
            ffmpeg
            .output(audio, tmp_wav, **{'f': 's16le', 'ar': arate, 'ac': 2})
            .run(cmd=ffmpeg_path, quiet=True, overwrite_output=yes, capture_stderr=True)
        )
        #audio = ffmpeg.input(tmp_wav, **{'f': 's16le', 'ar': arate, 'ac': 2}).audio # setting -ar here fails. why?
        audio = ffmpeg.input(tmp_wav, **{'f': 's16le', 'ac': 2}).audio

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
            audio = ffmpeg.filter(audio, filter_name, **kwargs_filter)
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
            if fileext != '.dv':
                copy_exifdata(input, output)
                append_exifcomment(output, f'{datetime.now().isoformat(timespec="seconds")} : {arg0} ')
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
    parser.add_argument('-b', '--begin', dest='sec_begin', metavar='sec', type=float, default=1.0, help='Begin rendering date/time, in second')
    parser.add_argument('-l', '--len', dest='sec_len', metavar='sec', type=float, default=4.0, help='Duration of rendering date/time. No end if negative')
    parser.add_argument('-v', '--vpos', dest='text_vpos', metavar='t/b', choices=['t','b'], default="b", help='Render text at top or bottom')
    parser.add_argument('--font', metavar='path', default=None, help='Full path to a font file')
    parser.add_argument('-t', '--tc', dest='show_tc', action='store_true', default=False, help='Render timecode rather than time in HH:MM')
    parser.add_argument('--date', dest='show_date', action=argparse.BooleanOptionalAction, default=True, help='Render date or not')
    parser.add_argument('--time', dest='show_time', action=argparse.BooleanOptionalAction, default=True, help='Render time or not')
    parser.add_argument('--datetime', dest='datetime_opt', metavar='str', default='', help='Use given "yyyy-mm-dd[ HH:MM[:SS]]" as date/time')
    parser.add_argument('--offset', metavar='[-]hh:mm', default=None, help='Offset time. Ex: " -9:00" (space required when - used)')
    parser.add_argument('--guess', action='store_true', default=False, help='Guess offset from filename and recording time')
    parser.add_argument('--vf', '-vf', dest='args_vfilter', metavar='args', action='append', default=[], help='Video filter. Ex "scale=w=iw/2:h=ih/2"')
    parser.add_argument('--af', '-af', dest='args_afilter', metavar='args', action='append', default=[], help='Audio filter. Ex "afftdn=nr=10:nf=-40"')
    parser.add_argument('--encode', dest='args_encode', metavar='args', default='', help='Encode arguments. Ex " -c:v libx264 -preset slow -c:a ac3"')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='Yes to overwrite')
    parser.add_argument('--ffmpeg', metavar='path', default=None, help='Full path to ffmpeg')
    parser.add_argument('--bug', action='store_true', default=False, help='Bug workaround. Try it when "Assertion cur_size >= size"')
    parser.add_argument('--simulate', action='store_true', default=False, help='Print generated ffmpeg command, no execution')
    parser.add_argument('-e', '--ext', dest='optext', metavar='ext', default=None, help='File extension for output (dv, mov, mp4 etc)')
    parser.add_argument('infiles', nargs='+', type=str, help='Input movie files')
    parser.add_argument('output', help='Output dir or file')

    args = parser.parse_args(args=argv)
    args.arg0 = ' '.join([x.replace(' ', '\\ ') for x in argparse._sys.argv])

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
