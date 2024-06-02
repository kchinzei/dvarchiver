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
from _util import get_mediainfo, get_datetime_fromstr, get_datetime_fromfile, datetime2fname, guess_offset
from typing import Any, Container, Iterable, List, Dict, Optional, Union


def get_datetime(path: str,
                datetime_opt: Optional[str] = '',
                offset: Optional[str|None] = None) -> datetime:
    '''
    Obtain Recorded Date and return datetime.
    Internally uses mediainfo
    '''
    
    dt = get_datetime_fromstr(datetime_opt)
    if dt is None:
        dt = get_datetime_fromfile(path, offset)
    return dt


def touch_datetime(path: str,
                datetime_opt: Optional[str] = '',
                offset: Optional[str|None] = None,
                simulate: Optional[bool] = False,
                **kwargs: Any):
    '''
    Touch movie file using Recorded Date.
    Internally uses mediainfo
    '''
    
    dt = get_datetime(path, datetime_opt, offset)
    if dt is None:
        print(f'Fail to get recorded date from {path} and you did not provide datetime as option.', file=sys.stderr)
        return 1
    if simulate:
        print(f'os.utile {path}   {dt}')
    else:
        # Set modify timestamp
        cr_time = dt.timestamp()
        os.utime(path, (cr_time, cr_time))


def mv_datetime(path: str,
                datetime_opt: Optional[str] = '',
                offset: Optional[str|None] = None,
                simulate: Optional[bool] = False,
                yes: Optional[bool] = False,
                **kwargs: Any):
    '''
    Rename a movie file using Recorded Date.
    Internally uses mediainfo
    '''
    global formatstr
    
    # General / Recorded date appears like 2005-07-02 09:48:06 in localtime
    dt = get_datetime(path, datetime_opt, offset)
    if dt is None:
        print(f'Fail to get recorded date from {path} and you did not provide datetime as option.', file=sys.stderr)
        return 1
    fstem = datetime2fname(dt)

    # Rename
    dirpath = os.path.dirname(path)
    _, fileext = os.path.splitext(path)
    to = os.path.join(dirpath, fstem + fileext)
    if simulate:
        print(f'{path}  ==>  {to}')
    else:
        if yes:
            os.replace(path, to)
        else:
            os.rename(path, to)
        # Set modify timestamp
        cr_time = dt.timestamp()
        os.utime(to, (cr_time, cr_time))

    
def main(argv: Optional[List[str]] = None) -> int:
    global formatstr
    
    if sys.version_info < REQUIRED_PYTHON_VERSION:
        print(f'Requires python {REQUIRED_PYTHON_VERSION} or newer.', file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser(description='Rename (mv) movie files using Recorded Date field',
                                                 fromfile_prefix_chars='+')

    #parser.add_argument('--format', metavar='str', default=None, help=f'Custom format string, default="{formatstr}"')
    parser.add_argument('--datetime', dest='datetime_opt', metavar='str', type=str, default='', help='Use given "yyyy-mm-dd[ HH:MM[:SS]]" as date/time')
    parser.add_argument('--offset', metavar='[-]hh:mm', default=None, help='Offset time. Ex: " -9:00" (space required when - used)')
    parser.add_argument('--guess', action='store_true', default=False, help='Print offset between filename and recording time, no file change')
    parser.add_argument('--touch', action='store_true', default=False, help='Modify file modification time only')
    parser.add_argument('--simulate', action='store_true', default=False, help='Print generated command, no file change')
    parser.add_argument('-y', '--yes', action='store_true', default=False, help='Yes to overwrite.')
    parser.add_argument('infiles', nargs='+', type=str, help='Input movie files')

    args = parser.parse_args(args=argv)

    #if args.format is not None:
    #    formatstr = args.format

    for path in args.infiles:
        args.path = path
        if args.guess:
            dif = guess_offset(path)
            print(f'{dif} : {path}')
        elif args.touch:
            touch_datetime(**vars(args))
        else:
            mv_datetime(**vars(args))
    return 0

if __name__ == '__main__':
    sys.exit(main())
    
