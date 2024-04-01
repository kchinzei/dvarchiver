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
Input movies are assumed in DV (digital video) format.
'''

import argparse
import sys
import os
import re
import subprocess
import datetime
import ffmpeg # Need ffmpeg-python (not other similar ones)
from typing import Any, Container, Iterable, List, Dict, Optional, Union

DEFAULT_FONTFILE = 'CRR55.TTF'


def which(cmd: str) -> str:
    p = subprocess.run(['which', cmd], check=True, text=True, stdout=subprocess.PIPE)
    path = p.stdout.split('\n')[0]
    if path == '' or 'not found' in path:
        print(f'Required command {cmd} not found', file=sys.stderr)
        return 1
    return path

cwd = os.path.dirname(os.path.realpath(__file__))

# Global variable
font = os.path.join(cwd, 'font', DEFAULT_FONTFILE)
mediainfo = which('mediainfo')

def get_mediainfo(path: str, field: str) -> str:
    '''
    Run mediainfo to get information of the movie in path.
    '''
    global mediainfo
    p = subprocess.run([mediainfo, f'--Output={field}', path], check=True, text=True, stdout=subprocess.PIPE)
    return p.stdout.split('\n')[0]

def render_datetime(input: str,
                    output: str,
                    sec_begin: Optional[float] = 1.0,
                    sec_len: Optional[float] = 4.0,
                    show_tc: Optional[bool] = False,
                    show_date: Optional[bool] = True,
                    show_time: Optional[bool] = True,
                    datetime_opt: Optional[str] = '',
                    text_size: Optional[int] = 5,
                    text_color: Optional[str] = 'white',
                    text_vpos: Optional[str] = 'b',
                    yes: Optional[bool] = False,
                    **kwargs: Any):
    '''
    Render date/time to a movie file.
    Internally uses ffmpeg and mediainfo
    '''
    global font

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
    date_s = hh_s = mm_s = ss_s = ''
    m = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d)( (\d\d):(\d\d)(:(\d\d))?)?', datetime_opt)
    if m is not None:
        year_s = m.group(1)
        month_s = m.group(2)
        day_s = m.group(3)
        hh_s = m.group(5)
        mm_s = m.group(6)
        ss_s = m.group(8)
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

    # Font size / position
    height = int(get_mediainfo(input, 'Video;%Height%'))
    text_size = height * text_size / 100
    if text_vpos == 't':
        ypos = '2*lh'
    else:
        ypos = 'h-(2*lh)'

    # 3) Special workaround for DV
    # ffmpeg creation_time convert time to UTC. This is fine, but But Sony DV format seems assuming localtime.
    # Need 'Z' to prevent ffmpeg converting local timezone to UTC.
    # cf: https://video.stackexchange.com/questions/25568/what-is-the-correct-format-of-media-creation-time
    # Saving DV requires target. We assume here NTSC.
    datetime_s = f'{year_s}-{month_s}-{day_s} {hh_s}:{mm_s}:{ss_s}'
    kwargs_output = {}
    _, fileext = os.path.splitext(output)
    if fileext == '.dv':
        kwargs_output = {'metadata': f'creation_time={datetime_s}Z', 'target': 'ntsc-dv'}
    else:
        kwargs_optput = {'metadata': f'creation_time={datetime_s}'}
            
    # 4) Render output movie
    #    Do it async
    in_mov = ffmpeg.input(input)
    audio = in_mov['a:0'] # Need to drop two or more audio streams if exist.
    video = in_mov.video
    process = (
        ffmpeg
        .drawtext(video, x='w*0.02', y=ypos, fontfile=font, fontsize=text_size, fontcolor=text_color, borderw=2, **kwargs_date)
        .drawtext(x='(w-tw)-(w*0.02)', y=ypos, fontfile=font, fontsize=text_size, fontcolor=text_color, borderw=2, **kwargs_time)
        .output(audio, output, **kwargs_output)
        .run_async(quiet=True, overwrite_output=yes, pipe_stderr=True)
    )
    stderr = process.communicate()
    # print(f' -- stderr: {stderr.decode('utf-8')}', file=sys.stderr)
    return process.returncode
    

def main(argv: Optional[List[str]] = None) -> int:
    global font
    
    if sys.version_info < REQUIRED_PYTHON_VERSION:
        print(f'Requires python {REQUIRED_PYTHON_VERSION} or newer.', file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description='Render date/time to the given movie files',
                                                 fromfile_prefix_chars='+')

    parser.add_argument('-s', '--size', dest='text_size', metavar='%', type=float, default="5", help='Font size in %%')
    parser.add_argument('-c', '--color', dest='text_color', metavar='str', default="white", help='Text color (yellow, etc)')
    parser.add_argument('-b', '--begin', dest='sec_begin', metavar='sec', type=float, default=1.0, help='Begin rendring date/time, in second')
    parser.add_argument('-l', '--len', dest='sec_len', metavar='sec', type=float, default=4.0, help='Duration of rendring date/time. No end if negative')
    parser.add_argument('-v', '--vpos', dest='text_vpos', metavar='t/b', choices=['t','b'], default="b", help='Render text at top or bottom')
    parser.add_argument('-t', '--tc', dest='show_tc', action='store_true', default=False, help='Render timecode rather than HH:MM')
    parser.add_argument('--date', dest='show_date', action=argparse.BooleanOptionalAction, default=True, help='Render date')
    parser.add_argument('--time', dest='show_time', action=argparse.BooleanOptionalAction, default=True, help='Render time')
    parser.add_argument('--datetime', dest='datetime_opt', metavar='str', type=str, default='', help='Use given "yyyy-mm-dd[ HH:MM[:SS]]" as date/time')
    parser.add_argument('--font', dest='font_path', metavar='path', type=str, default=None, help='Full path to a font file')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='Yes to overwrite.')
    parser.add_argument('infiles', nargs='+', type=str, help='Input movie files')
    parser.add_argument('output', help='Output dir or file')

    args = parser.parse_args(args=argv)
    args.arg0 = ' '.join(argparse._sys.argv)

    if args.font_path is not None:
        font = args.font_path

    for path in args.infiles:
        args.input = path
        render_datetime(**vars(args))
    return 0

if __name__ == '__main__':
    sys.exit(main())
