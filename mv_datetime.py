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
Rename (mv) given DV (digital video) files by its embedded date/time information.
For example, 2001-01-01_1200_00.dv
Input movies are assumed to have Recorded Date field found by 'mediainfo'.
'''

import argparse
import sys
import os
from datetime import datetime
from _util import get_mediainfo, get_datetime_fromstr, get_datetime_fromfile
from typing import Any, Container, Iterable, List, Dict, Optional, Union

formatstr = '{}-{}-{}_{}{}_{}' # replaced by yyyy, mm, dd, HH, MM, SS


def datetime2strs(dt: datetime) -> tuple[str, str, str, str, str, str]:
    return f'{dt.year}', f'{dt.month:02}', f'{dt.day:02}', f'{dt.hour:02}', f'{dt.minute:02}', f'{dt.second:02}'


def mv_datetime(path: str,
                datetime_opt: Optional[str] = '',
                offset: Optional[str|None] = None,
                yes: Optional[bool] = False,
                **kwargs: Any):
    '''
    Rename a movie file using Recorded Date.
    Internally uses mediainfo
    '''
    global formatstr
    
    # General / Recorded date appears like 2005-07-02 09:48:06 in localtime
    dt = get_datetime_fromstr(datetime_opt)
    if dt is None:
        dt = get_datetime_fromfile(input, offset)
    if dt is None:
        print(f'Fail to get recorded date from {input} and you did not provide datetime as option.', file=sys.stderr)
        return 1
    y0, m0, d0, hh0, mm0, ss0 = datetime2strs(dt)

    # Rename
    dirpath = os.path.dirname(path)
    _, fileext = os.path.splitext(path)
    to = os.path.join(dirpath, formatstr.format(y0, m0, d0, hh0, mm0, ss0) + fileext)
    if yes:
        os.replace(path, to)
    else:
        os.rename(path, to)
    # todo: error handling
    #print(f'{mv} {'-f' if yes else '-i'} {path} {to}')

    # Set modify timestamp
    d = datetime.datetime(int(y0), int(m0), int(d0), int(hh0), int(mm0), int(ss0))
    cr_time = d.timestamp()
    os.utime(to, (cr_time, cr_time))

    
def main(argv: Optional[List[str]] = None) -> int:
    global formatstr
    
    if sys.version_info < REQUIRED_PYTHON_VERSION:
        print(f'Requires python {REQUIRED_PYTHON_VERSION} or newer.', file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description='Rename (mv) movie files using Recorded Date field',
                                                 fromfile_prefix_chars='+')

    parser.add_argument('--format', metavar='str', default=None, help=f'Custom format string, default="{formatstr}"')
    parser.add_argument('--datetime', dest='datetime_opt', metavar='str', type=str, default='', help='Use given "yyyy-mm-dd[ HH:MM[:SS]]" as date/time')
    parser.add_argument('--offset', metavar='[-]hh:mm', default=None, help='Offset time. Ex: "8:00"')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='Yes to overwrite.')
    parser.add_argument('infiles', nargs='+', type=str, help='Input movie files')

    args = parser.parse_args(args=argv)

    if args.format is not None:
        formatstr = args.format

    for path in args.infiles:
        args.path = path
        mv_datetime(**vars(args))
    return 0

if __name__ == '__main__':
    sys.exit(main())
    
