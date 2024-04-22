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
import re
import subprocess
import datetime
from typing import Any, Container, Iterable, List, Dict, Optional, Union

mediainfo_path = 'mediainfo'
formatstr = '{}-{}-{}_{}{}_{}' # replaced by yyyy, mm, dd, HH, MM, SS

def get_mediainfo(path: str, field: str) -> str:
    '''
    Run mediainfo to get information of the movie in path.
    '''
    global mediainfo_path
    p = subprocess.run([mediainfo_path, f'--Output={field}', path], check=True, text=True, stdout=subprocess.PIPE)
    return p.stdout.split('\n')[0]

def mv_datetime(path: str,
                datetime_opt: Optional[str] = '',
                yes: Optional[bool] = False,
                **kwargs: Any):
    '''
    Rename a movie file using Recorded Date.
    Internally uses mediainfo
    '''
    global formatstr
    
    # General / Recorded date appears like 2005-07-02 09:48:06 in localtime
    datetime_s = get_mediainfo(path, 'General;%Recorded_Date%')
    year_s = month_s = day_s = hh_s = mm_s = ss_s = ''
    m = re.match(r'^(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d)(:(\d\d))?', datetime_opt)
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
            print(f'Fail to get recorded date from {path} and you did not provide datetime as option.', file=sys.stderr)
            return 1
        year_s = m.group(1)
        month_s = m.group(2)
        day_s = m.group(3)
        hh_s = m.group(4)
        mm_s = m.group(5)
        ss_s = m.group(6)

    # Rename
    dirpath = os.path.dirname(path)
    _, fileext = os.path.splitext(path)
    to = os.path.join(dirpath, formatstr.format(year_s, month_s, day_s, hh_s, mm_s, ss_s) + fileext)
    if yes:
        os.replace(path, to)
    else:
        os.rename(path, to)
    # todo: error handling
    #print(f'{mv} {'-f' if yes else '-i'} {path} {to}')

    # Set modify timestamp
    d = datetime.datetime(int(year_s), int(month_s), int(day_s), int(hh_s), int(mm_s), int(ss_s))
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
    
