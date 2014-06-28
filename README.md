# Sort photo and video files according to date

## Overview

This command line tool helps to organize media files from your
camera by date and time. It moves (or copies) source files
to destination directory sorting them by subdirs like
'$YEAR/$YEAR-$MONTH-$DAY/$HOUR:$MINUTE:$SECOND $FILENAME'.
For the case when date/time on your camera is not set
correctly, you can correct sorting results supplying
date/time shifting command line options.

## Examples

Copy files to new location, be verbose:

    $ sort-media /path/to/unsorted/media /destination/path

Silently move files to new location:

    $ sort-media --quiet --move /path/to/unsorted/media /destination/path

Do nothing, just report what will be done:

    $ sort-media --dry-run --move /path/to/unsorted/media /destination/path

Sort files, applying date/time shifting:

    $ sort-media --year-shift=-2 --hour-shift=4 /path/to/unsorted/media /destination/path

Show usage:

    $ sort-media

or

    $ sort-media --help

## Dependencies

* python;
* python-exif (to extract meta from images);
* ffmpeg (to extract meta from movies).
