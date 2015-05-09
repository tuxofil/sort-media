#!/usr/bin/env python

"""
This script helps to sort images and videos by date and time.

It searches given source directory recursively for media files
(images and movies), fetch date and time information from them and
copies it (or moves, see '--move' command line option) to destination
directory.

New file location for arbitrary FILENAME will look like:
"DESTINATION_DIR/YEAR/YEAR-MONTH-DAY/HOUR:MIN:SEC_FILENAME".

The FILENAME also will be lowered in case and destination file will
be chmoded (to 0644 by default, see '--chmod' command line option).

Additional features: you can sort your files from cameras with
badly supported date and time. You can define time shifting with
command line options. The media files metainfo will NOT be affected
by this shifting but only new file locations and names.

Command line arguments and options. Invoke the script with a single
'--help' option to see brief cheat-sheet.

Dependencies:

You need python-exif package to fetching date time from images to work.

You need ffmpeg installed to be able to fetch date and time
information from movies.
"""

import sys
import getopt
import os
import os.path
import time
import datetime
import shutil
import subprocess
import EXIF

SUPPORTED_VIDEO_EXTENSIONS = ['avi', 'mpg', 'mp4', '3gp', 'mov', 'm4v']
SUPPORTED_IMAGE_EXTENSIONS = ['jpeg', 'jpg', 'png', 'tif', 'tiff']

# Unfortunately, there is no package like python-ffmpeg (or pyffmpeg
# from Google) so I decided to call ffmpeg directly through the shell.
# It's not a big overhead for time-to-time task, really.
FETCH_VIDEO_DATETIME_CMD = \
    'ffmpeg -y -v quiet -i "{0}" -f ffmetadata - | ' + \
    'grep creation_time | sed -r \'s/^.+=//\' | ' + \
    'sed -r \'s/(-|:)/ /g\''

# ----------------------------------------------------------------------
# internal definitions

quiet = False
dry_run = False
debug = False
files_mode = 0644
remove_cleared_dirs = True

ACTION_COPY = 'copy'
ACTION_MOVE = 'move'
action = ACTION_COPY

time_shift = {
    'days' : 0,
    'hours' : 0,
    'minutes' : 0,
    'seconds' : 0
    }

SUPPORTED_EXTENSIONS = \
    SUPPORTED_VIDEO_EXTENSIONS + SUPPORTED_IMAGE_EXTENSIONS

def usage():
    """
    Print short help meesage.
    """
    print('Usage:')
    print('  ' + sys.argv[0] + ' --help')
    print('  ' + sys.argv[0] + ' [options] /src/dir/path /dst/dir/path')
    print('Options:')
    print('  --move     move files (will remove source files);')
    print('  --quiet    be quiet;')
    print('  --dry-run  do nothing, only report files and dirs processing;')
    print('  --dnrcd    do not remove cleared directories;')
    print('  --chmod=Octal permissions for new files. Default is 0644.')
    print('Time shifting options:')
    print('  --year-shift=Integer')
    print('  --month-shift=Integer')
    print('  --day-shift=Integer')
    print('  --hour-shift=Integer')
    print('  --minute-shift=Integer')
    print('  --second-shift=Integer')
    sys.exit(1)

def err(message):
    """
    Print the message to the stderr stream.

    :param message: the message to print
    :type message" string
    """
    sys.stderr.write('Error: {0}\n'.format(message))

def warn(message):
    """
    Print the message to the stderr stream.

    :param message: the message to print
    :type message" string
    """
    sys.stderr.write('Warning: {0}\n'.format(message))

def info(message):
    """
    Print the message to the stdout stream. If quiet
    mode is enabled, just do nothing.

    :param message: the message to print
    :type message" string
    """
    if not quiet:
        sys.stdout.write(message)

def dbg(message):
    """
    Print the message to the stdout stream. If quiet
    mode is enabled, just do nothing.

    :param message: the message to print
    :type message" string
    """
    if debug:
        sys.stdout.write('DEBUG: {0}\n'.format(message))

def process_dir(src_path, dst_path):
    """
    Do process files from source directory (src_path) and
    move/copy them to destination directory (dst_dir).

    :param src_path: source directory path
    :type src_path: string
    :param dst_path: destination directory path
    :type dst_path: string
    """
    info('entering {0}\n'.format(src_path))
    (files, dirs) = listdir(src_path)
    items_count = len(files) + len(dirs)
    for i in files:
        abs_i = os.path.join(src_path, i)
        info('  processing {0}: '.format(abs_i))
        dates = get_media_file_date_time(abs_i)
        if dates is not None:
            (orig_datetime, shifted_datetime) = dates
            dst_media_path = get_dst_media_path(dst_path, i, orig_datetime,
                                                shifted_datetime)
            if not dry_run:
                mkdirP(os.path.dirname(dst_media_path))
            if action == ACTION_COPY:
                info('copying to {0}...'.format(dst_media_path))
                if dry_run:
                    info('OK (dry run)\n')
                else:
                    try:
                        shutil.copy(abs_i, dst_media_path)
                        os.chmod(dst_media_path, files_mode)
                        info('OK\n')
                    except Exception as e:
                        info('error: {0}\n'.format(e))
            elif action == ACTION_MOVE:
                info('moving to {0}...'.format(dst_media_path))
                if dry_run:
                    info('OK (dry run)\n')
                else:
                    try:
                        shutil.move(abs_i, dst_media_path)
                        os.chmod(dst_media_path, files_mode)
                        info('OK\n')
                    except Exception as e:
                        info('error: {0}\n'.format(e))
    for i in dirs:
        process_dir(os.path.join(src_path, i), dst_path)
    if remove_cleared_dirs and \
            items_count > 0 and \
            len(os.listdir(src_path)) == 0:
        info('removing empty directory: {0}\n'.format(src_path))
        try:
            os.rmdir(src_path)
        except Exception as e:
            warn(e)
    else:
        info('leaving {0}\n'.format(src_path))

def listdir(path):
    """
    List directory, filter supported files and
    return two lists: list of subdirectories and list of
    media files found.

    :param path: directory path
    :type path: string
    :rtype: tuple of two elements, where first element is
            list of media filenames (without path) and second
            element is list of subdirectories (without path).
    """
    files = list()
    dirs = list()
    for i in os.listdir(path):
        abs_i = os.path.join(path, i)
        if os.path.exists(abs_i):
            if os.path.isdir(abs_i):
                dirs.append(i)
            elif is_media(abs_i):
                files.append(i)
    files.sort()
    dirs.sort()
    return (files, dirs)

def is_media(path):
    """
    Check if given file is supported by the script.

    :param path: file path
    :type path: string
    :rtype: boolean
    """
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    return ext in SUPPORTED_EXTENSIONS and os.path.isfile(path)

def get_media_file_date_time(path):
    """
    Read creation date and time from given media file metadata.
    Requested time shifting will be applyed automatically.
    Return tuple (orig_datetime, shifted_datetime) on success,
    where orig_datetime and shifted_datetime is instance of
    datetime.datetime class.
    Return None if no date/time info found.

    :param path: media file path
    :type path: string
    :rtype: tuple or None
    """
    time_struct = None
    ext = os.path.splitext(path)[1].lstrip('.').lower()
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        with open(path, 'rb') as fd:
            exif_data = EXIF.process_file(fd)
            if not exif_data:
                info('no EXIF information found\n')
                return None
            # search for date and time
            for k in ['Image DateTime', 'EXIF DateTimeOriginal',
                      'EXIF DateTimeDigitized']:
                try:
                    time_struct = time.strptime(exif_data[k].printable,
                                                '%Y:%m:%d %H:%M:%S')
                    break
                except:
                    pass
    elif ext in SUPPORTED_VIDEO_EXTENSIONS:
        try:
            raw_datetime = sh(FETCH_VIDEO_DATETIME_CMD.format(path)).strip()
            time_struct = time.strptime(raw_datetime, '%Y %m %d %H %M %S')
        except:
            pass
    dbg('time_struct: {0}'.format(time_struct))
    if time_struct is None:
        info('no date/time information found\n')
        return None
    dbg('time_shift: {0}'.format(time_shift))
    timedelta = datetime.timedelta(**time_shift)
    dbg('timedelta: {0}'.format(timedelta))
    orig_datetime = datetime.datetime.fromtimestamp(time.mktime(time_struct))
    shifted_datetime = orig_datetime + timedelta
    dbg('shifted result: {0}'.format(shifted_datetime))
    if is_in_future(shifted_datetime):
        warn('Shifted datetime for {0} is in future ({1})'.format(
                path, shifted_datetime))
    return (orig_datetime, shifted_datetime)

def is_in_future(date_time):
    """
    Return True if given datetime is in future.

    :param date_time: tested datetime
    :type date_time: instance of datetime.datetime class
    :rtype: boolean
    """
    return (datetime.datetime.now() - date_time).total_seconds() < 0

def sh(command):
    """
    Run external command (with shell) and return stdout as string.
    If external command will fail (retcode != 0), None will be returned.

    :param command: external command to run
    :type command: string
    :rtype: string or None
    """
    p = subprocess.Popen([command], stdout = subprocess.PIPE,
                         stderr = subprocess.PIPE,
                         shell = True, env = {'LC_ALL' : 'C'})
    (stdout_data, stderr_data) = p.communicate()
    retcode = p.wait()
    if retcode == 0:
        return stdout_data
    info('\n')
    err('external command failed.\n' + \
            'The command was: {0}\n\n' + \
            'STDERR:\n{1}\n'.format(command, stderr_data))
    return None

def get_dst_media_path(rootdir_path, src_filename, orig_datetime,
                       shifted_datetime):
    """
    Create absolute path of new location for given media file.

    :param rootdir_path: destination root directory path
    :type rootdir_path: string
    :param src_filename: source media file basename
    :type src_filename: string
    :param orig_datetime: date and time info for media file (original)
    :type orig_datetime: instance of datetime.datetime class
    :param shifted_datetime: date and time info for media file (shifted)
    :type shifted_datetime: instance of datetime.datetime class
    :rtype: string
    """
    dst_filename = src_filename.lower()
    # hack for files, processed by first version of the program
    if dst_filename.startswith(orig_datetime.strftime('%H:%M_')):
        dst_filename = dst_filename[6:]
    # use file prefix based on time to sort files fetched
    # from various sources
    filename_prefix = shifted_datetime.strftime('%H:%M:%S_')
    if not dst_filename.startswith(filename_prefix):
        dst_filename = filename_prefix + dst_filename
    return os.path.join(
        rootdir_path,
        shifted_datetime.strftime('%Y'),
        shifted_datetime.strftime('%Y-%m-%d'),
        dst_filename)

def check_dir(path):
    """
    Check directory is exist.
    Halt script with error if it is not.

    :param path: directory path
    :type path: string
    """
    if not os.path.exists(path):
        err('"{0}" is not exist'.format(path))
        sys.exit(1)
    if not os.path.isdir(path):
        err('"{0}" is not a directory'.format(path))
        sys.exit(1)

def str_to_shift(string):
    """
    Cast string to time shift (integer).

    :param string: textual representation of integer
    :type string: string
    :rtype: int
    """
    try:
        return int(string)
    except:
        err('Bad integer: "{0}"'.format(string))
        sys.exit(1)

def mkdirP(path):
    """
    Analog to 'mkdir -p'.

    Implementation of os.makedirs() inconsistent with the documentation:
    the latter points as 'Like mkdir(), but makes all intermediate-level
    directories needed to contain the leaf directory' but in real life
    it creates *all* directories. I don't know what will be changed in
    next Python2.6 update - documentation or os.makedirs() implementation,
    so I decided to not use os.makedirs() at all.

    :param path: directory path
    :type path: string
    """
    if not path or os.path.isdir(path):
        return
    mkdirP(os.path.dirname(path))
    os.mkdir(path)

# ----------------------------------------------------------------------
# entry point

if __name__ == '__main__':
    """
    Script entry point
    """
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], '',
            ['move', 'help', 'dry-run', 'quiet', 'dnrcd', 'debug',
             'chmod=', 'year-shift=', 'month-shift=', 'day-shift=',
             'hour-shift=', 'minute-shift=', 'second-shift='])
    except getopt.GetoptError as e:
        err(e)
        usage()
    if len(args) == 0:
        usage()
    for o, v in opts:
        if o == '--help':
            usage()
        elif o == '--move':
            action = ACTION_MOVE
        elif o == '--quiet':
            quiet = True
        elif o == '--dry-run':
            dry_run = True
        elif o == '--debug':
            debug = True
        elif o == '--dnrcd':
            remove_cleared_dirs = False
        elif o == '--chmod':
            files_mode = int(v, 8)
        elif o == '--year-shift':
            time_shift['days'] += str_to_shift(v) * 365
        elif o == '--month-shift':
            time_shift['days'] += str_to_shift(v) * 30
        elif o == '--day-shift':
            time_shift['days'] += str_to_shift(v)
        elif o == '--hour-shift':
            time_shift['hours'] = str_to_shift(v)
        elif o == '--minute-shift':
            time_shift['minutes'] = str_to_shift(v)
        elif o == '--second-shift':
            time_shift['seconds'] = str_to_shift(v)
    if len(args) != 2:
        err('bad arguments')
        sys.exit(1)
    src_dir = args[0]
    dst_dir = args[1]
    check_dir(src_dir)
    check_dir(dst_dir)
    process_dir(src_dir, dst_dir)

