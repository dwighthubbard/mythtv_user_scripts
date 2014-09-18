#!/usr/bin/env python
"""
Rename mythtv recordings
"""
from __future__ import print_function
import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', help="Destination directory for the links")
    parser.add_argument("--live", help="Include live tv recordings", action="store_true")
    parser.add_argument('--v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('--maxlength', default=None, help='Max length for the filename (default None)')
    selection_group = parser.add_argument_group("Recording Selection")
    selection_group.add_argument('--channel-id', '--chanid', help='Specify the channel ID for the file to rename')
    selection_group.add_argument('--starttime', help='Only link the file with the specified starttime')
    selection_group.add_argument('--filename', help='Only link the specified file')
    parser.add_argument_group(selection_group)
    format_group = parser.add_argument_group('File Naming Options')
    format_group.add_argument('--file_format', default="{title}{delimiter}{start}{delimiter}{subtitle}")
    format_group.add_argument('--time_format', default="%Y%m%d-%H:%M:%S")
    format_group.add_argument('--delimiter', '--separator', default='-', help='Delimeter character')
    format_group.add_argument('--whitespace', default=' ', help='Whitespace character')
    parser.add_argument_group(format_group)
    args = parser.parse_args()
    print(args)