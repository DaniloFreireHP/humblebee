#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
import os
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time
from errno import ENOENT


from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

from util import zero_prefix_int, timestamp
from tverror import WTFException
from parser import ez_parse_episode as parse_file



log = logging.getLogger('tvunfucker')

class FileSystem(LoggingMixIn, Operations):

    filename_mask_ep = (
       ' %(series_title)s s%(season_number)se%(ep_number)s%(extra_ep_number)s %(title)s%(ext)s'
       )
    filename_mask_season = 's%(season_number)s'
    
    def __init__(self, db):
        #files will be taken straight from db, no stupid shit
        self.db = db
        pass

    def readdir(self, path, fh):
        log.debug('path: %s', path)

        defret = ['.', '..']
        pathpcs = self._split_path(path)

        if path == '/':
            rows = self.db.get_series_plural()
            return defret+[row['title'] for row in rows]
        elif len(pathpcs) == 1: #series
            rows = self.db.get_seasons(series_title=pathpcs[0])

            ret = defret

            for row in rows:
                row = dict(row)
                row['season_number'] = zero_prefix_int(row['season_number'])
                ret.append(self.filename_mask_season % row)
            return ret
        elif len(pathpcs) == 2: #season, get eps
            f = parse_file(path)            
            rows = self.db.get_episodes(
                season_number=f['season_num'],
                series_title=pathpcs[0]
                )
            ret = defret
            for row in rows:
                row = dict(row)
                nums = ('season_number', 'ep_number', 'extra_ep_number')
                for num in nums:
                    row[num]=zero_prefix_int(row[num])                
                row['ext'] = os.path.splitext(row['file_path'])[1]
                if not row['extra_ep_number']:
                    row['extra_ep_number'] = ''
                ret.append(self.filename_mask_ep % row)
            return ret

    def getattr(self, path, fh=None):
        log.debug('path: %s', path)

        now = time()

        dirmode = {
                'st_mode':(S_IFDIR | 0755),
                'st_ctime' : now,
                'st_mtime' : now,
                'st_atime' : now,
                'st_nlink' : 2
                }
        filemode = {
                'st_mode':(S_IFREG | 0755),
                'st_ctime' : now,
                'st_mtime' : now,
                'st_atime' : now,
                'st_nlink' : 2
                }

        pathpcs = self._split_path(path)

        def check_rows(rows):
            if not rows:
                raise FuseOSError(ENOENT)
            elif len(rows) > 1:
                raise WTFException(
                    'filename %s has more than one candidate' % pathpcs[0]
                    )
            return rows[0]
            
        def make_ret(row, mode='dir'):
            l = dirmode if mode=='dir' else filemode
            l.update({
                    'st_ctime':timestamp(row['created_time']),
                    'st_mtime':timestamp(row['modified_time'])
                    })
            return l

        if path == '/': #root
            return dirmode

        elif path == '/_unparsed':
            raise FuseOSError(ENOENT)

        elif len(pathpcs) == 1: #series_dir
            rows = self.db.get_series_plural(
                title=pathpcs[0]
                )
            row = check_rows(rows)
            return make_ret(row)
        elif len(pathpcs) == 2: #season dir
            f = parse_file(path)

            log.debug('Prased ep: %s', f)
            rows = self.db.get_seasons(
                series_title = pathpcs[0],
                season_number = f['season_num']
                )
            log.debug('Found seasons: %s', rows)
            return make_ret(check_rows(rows))
        elif len(pathpcs) == 3: #episode file
            f = parse_file(path)
            log.debug('Prased ep: %s', f)
            rows = self.db.get_episodes(
                season_number=f['season_num'],
                series_title=pathpcs[0],
                ep_number=f['ep_num']
                )
            return make_ret(check_rows(rows), 'file')

        

    def chmod(self, path, mode):
        return 0

    def chown(self, path, mode):
        return 0

    def _split_path(self, path):
        return path.strip('/').split('/')

    

    

    
