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

import sys
import os
import re
import subprocess
from datetime import datetime, timedelta
from exiftool import ExifToolHelper
from typing import Any, Container, Iterable, List, Dict, Optional, Union

#import logging
#logging.basicConfig(level=logging.DEBUG)

EXIF_KEY_HINTS = ['CreateDate', 'ModifyDate', 'DateTimeOriginal', 'OffsetTime', 'Aperture', 'Gain', 'Exposure', 'WhiteBalance', 'ISO', 'ImageStabilization', 'FNumber', 'Shutter', 'FrameRate', 'Rotation', 'GPS', 'Make', 'Model', 'MajorBrand', 'MinorVersion', 'CompatibleBrands', 'FileFunctionFlags', 'UserComment']


def get_mediainfo(path: str, field: str) -> str:
    '''
    Run mediainfo to get information of the movie in path.
    '''
    p = subprocess.run(['mediainfo', f'--Output={field}', path], check=True, text=True, stdout=subprocess.PIPE)
    return p.stdout.split('\n')[0]


def get_exifdata(path: str, field: str) -> str|None:
    with ExifToolHelper() as etool:
        data = etool.get_tags(path, field)
        tags = [val for key,val in data[0].items() if field in key]
        if len(tags) > 0:
            return tags[0]
    return None

def set_exifdata(path: str, field: str, val: str):
    with ExifToolHelper() as etool:
        etool.set_tags(path, {field: val})

def copy_exifdata(pathfrom: str, pathto:str):
    with ExifToolHelper() as etool:
        data = etool.get_metadata(pathfrom)
        datatocopy = {key:val for key, val in data[0].items() for keypart in EXIF_KEY_HINTS if keypart in key}
        etool.set_tags(pathto, datatocopy)


def append_exifcomment(pathto: str, text:str):
    comment = get_exifdata(pathto, 'UserComment')
    if comment is None:
        comment = ''
    set_exifdata(pathto, 'UserComment', f'{text}\n{comment}')


def get_datetime_fromstr(datetime_str: str) -> datetime|None:
    m = re.match(r'^(\d\d\d\d)[-|:](\d\d)[-|:](\d\d)( (\d\d):(\d\d)(:(\d\d))?)?', datetime_str)
    if m is None:
        return None
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
    return datetime(int(year_s), int(month_s), int(day_s), int(hh_s), int(mm_s), int(ss_s))


def get_datetime_fromfile(path: str, offset: Optional[str] = None) -> datetime|None:
    datetime_str = get_mediainfo(path, 'General;%Recorded_Date%')
    dt = get_datetime_fromstr(datetime_str)
    if dt is None:
        datetime_str = get_exifdata(path, 'DateTimeOriginal')
        dt = get_datetime_fromstr(datetime_str)
        if dt is None:
            return None
    if offset is not None:
        m = re.fullmatch(r'([+|-]?)(0?\d):(\d\d)(:(\d\d))?', offset.strip())
        if m is not None:
            polarity = m.group(1)
            hh_s = m.group(2)
            mm_s = m.group(3)
            ss_s = m.group(5)
            if ss_s is None:
                ss_s = '00'
            delta = timedelta(hours = int(hh_s), minutes = int(mm_s), seconds = int(ss_s))
            if polarity == '-':
                dt -= delta
            else:
                dt += delta
    return dt
