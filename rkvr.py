#!/usr/bin/env python3

import os
import re
import sys
sys.dont_write_bytecode = True

DIR = os.path.abspath(os.path.dirname(__file__))
CWD = os.path.abspath(os.getcwd())
REL = os.path.relpath(DIR, CWD)

REAL_FILE = os.path.abspath(__file__)
REAL_NAME = os.path.basename(REAL_FILE)
REAL_PATH = os.path.dirname(REAL_FILE)
if os.path.islink(__file__):
    LINK_FILE = REAL_FILE; REAL_FILE = os.path.abspath(os.readlink(__file__))
    LINK_NAME = REAL_NAME; REAL_NAME = os.path.basename(REAL_FILE)
    LINK_PATH = REAL_PATH; REAL_PATH = os.path.dirname(REAL_FILE)

NAME, EXT = os.path.splitext(REAL_NAME)

import tarfile
import shutil
import datetime, time
from glob import glob
from ruamel import yaml
from functools import lru_cache, partial
from collections import OrderedDict
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from leatherman.repr import __repr__
from leatherman.dbg import dbg
from leatherman.yaml import yaml_print, yaml_format

class UnknownActionError(Exception):
    def __init__(self, path):
        msg = f'error: unknown action={action}; not in actions={actions}'
        super().__init__(msg)

class NonExistantPathError(Exception):
    def __init__(self, path):
        msg = f'error: path={path} does not exist'
        super().__init__(msg)

class UnknownConfigNameError(Exception):
    def __init__(self, name):
        msg = f'error: unknown config name={name}'
        super().__init__(msg)

ACTIONS = [
    'bkup',
    'rmrf',
    'bkup-rmrf',
    'ls-bkup',
    'ls-rmrf',
]

def validate_action(action):
    if action not in ACTIONS:
        raise UnknownActionError(action, ACTIONS)

def check_paths(paths):
    def check_path(path):
        if os.path.exists(path):
            return os.path.abspath(path)
        raise NonExistantPathError(path)
    return [
        check_path(path)
        for path
        in paths
    ]

def mkdir_p(path):
    try:
        os.makedirs(path)
    except FileExistsError:
        pass

def rm_rf(path):
    if not os.path.exists(path):
        return
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)

class Archiver:
    def __init__(self, action=None, args=None, archive=None, sudo=None, keep=None, config=None):
        self.action = action
        self.args = args or []
        self.archive = archive
        self.sudo = sudo
        self.keep = keep
        self.config = config

    __repr__ = __repr__

    @property
    @lru_cache()
    def latest(self):
        return f'{self.archive}/latest'

    @property
    @lru_cache()
    def utc_offset(self):
        utc_offset_sec = time.altzone if time.localtime().tm_isdst else time.timezone
        return datetime.timedelta(seconds=-utc_offset_sec)

    @property
    @lru_cache()
    def now(self):
        return datetime.datetime.now().replace(microsecond=0, tzinfo=datetime.timezone(offset=self.utc_offset))

    @property
    @lru_cache()
    def timestamp(self):
        return self.now.isoformat()

    @property
    @lru_cache()
    def archive_timestamp(self):
        return f'{self.archive}/{self.timestamp}'

    @property
    @lru_cache()
    def archive_tar_gz(self):
        return f'{self.archive_timestamp}/archive.tar.gz'

    @property
    @lru_cache()
    def manifest_yml(self):
        return f'{self.archive_timestamp}/manifest.yml'

    @property
    @lru_cache()
    def manifest(self):
        args = check_paths(self.args)
        manifest = OrderedDict()
        #manifest['timestamp'] = self.timestamp
        manifest['args'] = args
        files = []
        for arg in args:
            if os.path.isfile(arg):
                files += [arg]
            elif os.path.isdir(arg):
                for r, ds, fs in os.walk(arg):
                    files += [
                        os.path.join(r, f)
                        for f
                        in fs
                    ]
        manifest['files'] = sorted(files)
        return manifest

    @property
    @lru_cache()
    def manifests(self):
        return sorted(glob(f'{self.archive}/**/manifest.yml'))

    def execute(self):
        {
            'bkup': partial(self._archive, remove=False),
            'rmrf': partial(self._archive, remove=True),
            'bkup-rmrf': partial(self._archive, remove=True),
            'ls-bkup': self._display,
            'ls-rmrf': self._display,
        }[self.action]()

    def _harvest(self):
        harvested = []
        if self.keep not in (True, None):
            for manifest in self.manifests:
                path = os.path.dirname(manifest)
                timestamp = os.path.basename(path)
                if timestamp != 'latest':
                    moment = datetime.datetime.fromisoformat(timestamp)
                    duration = self.now - moment
                    if self.keep == False or duration.days > self.keep:
                        rm_rf(path)
                        harvested += [path]
#        if harvested:
#            for path in harvested:
#                print(path)
#            print(f'  -> /dev/null')

    def _display(self):
        results = []
        for manifest in self.manifests:
            if not os.path.islink(os.path.dirname(manifest)):
                manifest_yml = yaml.safe_load(open(manifest))
                results += [{
                    os.path.dirname(manifest): manifest_yml
                }]
        yaml_print(results)

    def _remove(self):
        for p in self.manifest['paths']:
            rm_rf(p)

    def _archive(self, remove=None):
        mkdir_p(self.archive_timestamp)
        # yaml_print(self.manifest)
        with open(self.manifest_yml, 'w') as f:
            f.write(yaml_format(self.manifest))
        with tarfile.open(self.archive_tar_gz, 'w:gz') as t:
            for f in self.manifest['files']:
                t.addfile(tarfile.TarInfo(f))
        if os.path.islink(self.latest):
            os.remove(self.latest)
        os.symlink(self.archive_timestamp, self.latest)
        if remove == True:
            self._remove()
        #print(f'-> {self.archive_timestamp}')
        print(self.archive_timestamp)
        self._harvest()

def config_path(name):
    if 'bkup' in name:
        name = 'bkup'
    elif 'rmrf' in name:
        name = 'rmrf'
    else:
        raise UnknownConfigNameError(name)
    return f'~/.config/{name}/{name}.yml'

def main(args=None):
    validate_action(LINK_NAME)
    parser = ArgumentParser(
        description=__doc__,
        formatter_class=RawDescriptionHelpFormatter,
        add_help=False)
    parser.add_argument(
        '--config',
        metavar='FILEPATH',
        default=config_path(LINK_NAME),
        help='default="%(default)s"; config filepath')
    ns, rem = parser.parse_known_args(args)
    try:
        config = dict([
            (k.replace('-', '_'), v)
            for k, v
            in yaml.safe_load(open(os.path.expanduser(ns.config))).items()
        ])
    except FileNotFoundError as er:
        config = dict()
    parser = ArgumentParser(
        parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument(
        'args',
        nargs='*',
        help='list of args; absolute or relative paths or partials')
    ns = parser.parse_args(rem)
    archiver = Archiver(action=LINK_NAME, **ns.__dict__)
    results = archiver.execute()

if __name__ == '__main__':
    main(sys.argv[1:])
