#!/usr/bin/python
import os
import sys
import tempfile
import getopt
import re
import socket
import logging
import argparse

logging.basicConfig(level=logging.DEBUG)
try:
    import MySQLdb
except ImportError:
    print 'This program requires the python MySQLdb module'
    sys.exit(10)


#Todo
# 1. Add code to verify prereqs including:
#   MySQLdb python module
#   mplayer
#   ffmpeg
#   mythtranscode
# 2. Add code to transcode to a second file for example use on ipod/cell-phone/etc


###########################################################
# Set some reasonable defaults
###########################################################
# Default number of lines to crop off the top
CUTCOMMERCIALS = False
CROPVIDEO = False
CROPTWICE = False
TRANSCODE = False
RUNAGAIN = False
KEEPORIGINAL = False
EXAMINEFRAMES = 0
TURBO = 213
MPEGQUALITY = 1800
MYTHRECORDINGSPATH = ['/var/lib/mythtv/recordings', '/usr/local/mythtv/recordings', '.']


# WORKDIRS is A list of directories we can use for temporary files, we will check if the directory exists and has
# adequate space and use the first directory from the list with enough room.
WORKDIRS = ['/tmp', '/work', '/var/lib/mythtv/recordings', '/usr/local/mythtv/recordings']


class video(object):
    def __init__(
            self, filename='', workdir='/var/lib/mythtv/recordings', logfile='/tmp/cleanupvideo.out',
            horizcrop=1, horizcroppercent=0, dbhost='localhost', dbuser='mythtv', dbpass='mythtv'
    ):
        self.filename = filename
        self.width = 0
        self.height = 0
        self.framerate = 0
        self.currentcrop = ''
        self.frames = 0
        self.horizcrop = horizcrop
        self.horizcroppercent = horizcroppercent
        self.croptop = 0
        self.cropleft = 0
        self.cropright = 0
        self.cropbottom = 0
        self.operationnumber = 0
        self.logfile = logfile
        self.workdir = workdir
        self.dbhost = dbhost
        self.dbuser = dbuser
        self.dbpass = dbpass

    def detectcropvalues(self, frames=0, horizcrop=-1, horizcroppercent=-1, turbo=TURBO):
        segmentsecs = 5
        if turbo < segmentsecs:
            turbo = segmentsecs * 2
        if horizcrop != -1:
            # This value is the number of 16 line blocks to crop from the top/bottom, so we need to multiply by 16
            self.horizcrop = int(horizcrop) * 16
        if horizcroppercent != -1:
            self.horizcroppercent = horizcroppercent
        if frames != 0:
            self.frames = frames
        cropsizes = {}
        crop = ''
        WIDTH = 0
        HEIGHT = 0
        edlfilename = '%s/cleanvideo_tmp.edl' % self.workdir
        edifilename = tempfile.mktemp('.edl', 'cleanupvideo_', self.workdir)
        fh = open(edifilename, 'w')
        for sec in range(1, 14000, turbo):
            fh.write('%d %d 0\n' % (sec, sec + (turbo - segmentsecs)))
        fh.close()
        if frames == 0:
            command = 'mplayer -quiet -edl %s -benchmark -nosound -vf cropdetect=24:16 -vo null %s 2> /dev/null' % (
            edifilename, self.filename)
        else:
            command = 'mplayer -quiet -edl %s -benchmark -nosound -vf cropdetect=24:16 -frames %d -vo null %s 2>/dev/null' % (
            edifilename, frames, self.filename)
        logging.debug('Running command:', command)
        for line in os.popen(command).readlines():
            splitline = line.strip().split()
            if len(splitline) > 3 and splitline[0] == 'VIDEO:':
                WIDTH = splitline[2].split('x')[0]
                HEIGHT = splitline[2].split('x')[1]
                self.framerate = splitline[5]
            if len(splitline) > 7 and splitline[0] == '[CROP]':
                crop = splitline[8][5:-2]
            try:
                cropsizes[crop] = cropsizes[crop] + 1
            except KeyError:
                cropsizes[crop] = 1
        currentcropcount = 0
        currentcrop = ''
        for crop in cropsizes.keys():
            if cropsizes[crop] > currentcropcount:
                currentcrop = crop
                currentcropcount = cropsizes[crop]
        if len(currentcrop):
            splitcrop = currentcrop.split(':')
            height = int(splitcrop[1])
            evenheight = (height / 16) * 16
            remainder = height - evenheight
            if horizcroppercent > 0:
                horizcrop = int(float(height) * (float(horizcroppercent) * .01))
            if remainder == horizcrop:
                currentcrop = '%d:%d:%d:%d' % (
                int(splitcrop[0]), int(splitcrop[1]) - (horizcrop / 2), int(splitcrop[2]),
                int(splitcrop[3]) + (horizcrop / 2))
            if remainder > horizcrop:
                currentcrop = '%d:%d:%d:%d' % (
                int(splitcrop[0]), int(splitcrop[1]) - (remainder / 2), int(splitcrop[2]),
                int(splitcrop[3]) + (remainder / 2))
            if remainder < horizcrop:
                currentcrop = '%d:%d:%d:%d' % (
                int(splitcrop[0]), evenheight - 16, int(splitcrop[2]), int(splitcrop[3]) + 8)
        self.width = int(WIDTH)
        self.height = int(HEIGHT)
        self.currentcrop = currentcrop
        if len(currentcrop):
            cropvalues = currentcrop.split(':')
            self.croptop = int(cropvalues[3])
            self.cropleft = int(cropvalues[2])
            self.cropright = self.width - (self.cropleft + int(cropvalues[0]))
            self.cropbottom = self.height - (self.croptop + (int(cropvalues[1])))
            if self.cropbottom < 0:
                self.cropbottom = 0
        logging.debug(
            'Crop borders are', self.width, self.height, self.croptop, self.cropleft, self.cropbottom, self.cropright)
        os.remove(edifilename)

    def createlockfile(self, completed=False):
        fh = open("%s.cleanupvideoran" % self.filename, 'w')
        fh.write('filename: %s\n' % self.filename)
        fh.write('hostname: %s\n' % socket.gethostname())
        #fh.write('cutcommercials: %d\n' % self.cutcommercials)
        #fh.write('cropvideo: %d\n' % self.cropvideo)
        fh.write('frames: %d\n' % self.frames)
        fh.write('horizcrop: %d\n' % self.horizcrop)
        fh.write('horizcroppercent: %d\n' % self.horizcroppercent)
        fh.write('completed: %d\n' % completed)
        fh.close()

    def deletelockfile(self):
        os.remove('%s.cleanupvideoran' % self.filename)

    def checklockfile(self):
        rc = 9
        try:
            fh = open("%s.cleanupvideoran" % self.filename, 'r')
        except IOError:
            return (2)
        for line in fh.readlines():
            if len(line):
                splitline = line.strip().split()
                if splitline[0] == 'completed:':
                    try:
                        rc = int(splitline[1])
                    except ValueError:
                        if splitline[1] == 'True':
                            rc = 1
                        else:
                            rc = 0
        return (rc)

    def swapfiles(self, keeporiginal=False):
        logging.debug(
            'Swapping files: %s/new.%s <-> %s' % (self.workdir, os.path.basename(self.filename), self.filename))
        if keeporiginal:
            for backupnumber in range(self.operationnumber, 999):
                try:
                    fh = open('%s/%s.%d' % (self.workdir, os.path.basename(self.filename), backupnumber))
                    fh.close()
                except IOError:
                    break
            try:
                fh = open('%s/new.%s' % (self.workdir, os.path.basename(self.filename)))
            except IOError:
                print 'New file did not get created'
                return (1)
            fh.close()
            os.rename(self.filename, '%s.old.%d' % (self.filename, backupnumber))
            # This doesn't work if the files aren't on the same device
            #os.rename('%s/new.%s' % (self.workdir,os.path.basename(self.filename),self.filename))
            os.system('mv %s/new.%s %s' % (self.workdir, os.path.basename(self.filename), self.filename))
        else:
            try:
                fh = open('%s/new.%s' % (self.workdir, os.path.basename(self.filename)))
            except IOError:
                print 'New file did not get created'
                return (1)
            fh.close()
            os.remove(self.filename)
            # This doesn't work if both files aren't on the same filesystem
            #os.rename('%s/new.%s' % (self.workdir,os.path.basename(self.filename)), self.filename)
            os.system('mv %s/new.%s %s' % (self.workdir, os.path.basename(self.filename), self.filename))
        self.operationnumber = self.operationnumber + 1
        return (0)

    def crop(self, keeporiginal=False, format='mp4', resize=False, mpegquality=MPEGQUALITY):
        if self.currentcrop == '':
            logging.debug('No crop boundries for this video object, running cropdetect')
            vid.detectcropvalues()
        if self.croptop == 0 and self.cropbottom == 0 and self.cropleft == 0 and self.cropright == 0:
            print 'No crop borders detected'
            return (0)
            # I am overriding the framerate here since it doesn't always get the correct framerate??
        vid.framerate = 29.97
        # Try it first just cropping, if it doesn't work try specifying the target format
        logging.debug(
            'Running command: ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d '
            '-aspect 16:9 -f mp4 -b %dkb "%s/new.%s"' % (
                self.logfile, self.filename, self.cropleft, self.cropright, self.croptop, self.cropbottom, mpegquality,
                self.workdir, os.path.basename(self.filename)
            )
        )
        rc = os.system(
            'ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -aspect 16:9 '
            '-f mp4 -b %dkb "%s/new.%s"' % (
                self.logfile, self.filename, self.cropleft, self.cropright, self.croptop, self.cropbottom, mpegquality,
                self.workdir, os.path.basename(self.filename)
            )
        ) >> 8
        if rc == 1:
            logging.debug(
                'Running command: ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d '
                '-cropbottom %d -target ntsc-dvd -aspect 16:9 -b %dkb "%s/new.%s"' % (
                self.logfile, self.filename, self.cropleft, self.cropright, self.croptop, self.cropbottom, mpegquality,
                self.workdir, os.path.basename(self.filename)))
            rc = os.system(
                'ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -target '
                'ntsc-dvd -aspect 16:9 -b %dkb "%s/new.%s"' % (
                self.logfile, self.filename, self.cropleft, self.cropright, self.croptop, self.cropbottom, mpegquality,
                self.workdir, os.path.basename(self.filename))) >> 8
            if rc == 1:
                logging.debug('Crop failed, returning failure code')
                return False
        self.swapfiles(keeporiginal)
        return True

    def cutcommercials(self, keeporiginal=False):
    # Commercial cutting is experimental and may not work as intended
        rc = os.system('mythcommflag > /dev/null 2>&1 -f %s' % self.filename) >> 8
        if rc > 126:
            print 'Commercial flagging failed for filename %s with error %d' % (self.filename, rc)
            return (1)
        rc = os.system('mythcommflag --gencutlist -f %s' % self.filename) >> 8
        if rc != 0:
            print 'Copying cutlist failed for %s with error %d' % (self.filename, rc)
            return (1)
        temppath = ''
        rc = os.system('mythtranscode --honorcutlist -i "%s" -o "%s/new.%s"' % (
        self.filename, self.workdir, os.path.basename(self.filename))) >> 8
        if rc != 0:
            print 'Cut commercials and transcoding failed for %s with error %d' % (self.filename, rc)
            return (2)
        self.swapfiles(keeporiginal)
        self.clearcutlist()

    def transcode(self, keeporiginal=False):
        rc = os.system('mythtranscode -i "%s" -o "%s/new.%s"' % (
        self.filename, self.workdir, os.path.basename(self.filename))) >> 8
        if rc != 0:
            print 'Transcoding failed for %s with error %d' % (self.filename, rc)
            return (2)
        self.swapfiles(keeporiginal)
        self.clearcutlist()

    def rebuildseeklist(self):
        rc = os.system('mythcommflag --video %s' % self.filename) >> 8
        if rc != 0:
            print 'Rebuilding seek list failed for %s with error %d' % (self.filename, rc)
            return (1)

    def clearcutlist(self):
        rc = os.system('mythcommflag --clearcutlist -f %s' % self.filename) >> 8
        conn = MySQLdb.connect(host=self.dbhost, user=self.dbuser, passwd=self.dbpass, db="mythconverg")
        cursor = conn.cursor()
        cursor.execute("UPDATE recorded SET cutlist=0,filesize=%ld WHERE basename='%s';" % (
        os.path.getsize(self.filename), os.path.basename(self.filename)))
        cursor.close()
        conn.close()
        if rc != 0:
            print 'Clearing cutlist failed for %s with error %d' % (self.filename, rc)
            return (1)

    def marktranscoded(self):
        conn = MySQLdb.connect(host=self.dbhost, user=self.dbuser, passwd=self.dbpass, db="mythconverg")
        cursor = conn.cursor()
        cursor.execute("update recorded set transcoded=1 where basename='%s';" % (os.path.basename(self.filename)))
        cursor.close()
        conn.close()


def deleteoldlocks(path=MYTHRECORDINGSPATH):
    if len(path) == 0:
        return
    for directory in path:
        try:
            files = os.listdir(directory)
            for file in files:
                if re.search('cleanupvideoran$', file) != None:
                    tempfile = '.'.join(file.split('.')[:-1])
                    if tempfile not in files:
                        logging.debug('Deleting old lock file: %s' % os.path.join(directory, file))
                        os.remove(os.path.join(directory, file))
        except OSError:
            pass


def deleteoldbackups(path=MYTHRECORDINGSPATH):
    if len(path) == 0:
        return
    for directory in path:
        try:
            files = os.listdir(directory)
            for file in files:
                if re.search('\.old\.*', file) != None:
                    tempfile = '.'.join(file.split('.')[:-2])
                    if tempfile not in files:
                        logging.debug('DEBUG: Deleting old backup file: %s' % os.path.join(directory, file))
                        os.remove(os.path.join(directory, file))
        except OSError:
            pass


def df(directory='/', humanreadable=False):
    if humanreadable == True:
        options = '-khP'
    else:
        options = '-kP'
    try:
        dfout = os.popen('df %s %s 2>/dev/null' % (options, directory)).readlines()[1]
    except IndexError:
        return 'None', 'None'
    splitline = dfout.split()
    return splitline[2], splitline[3]


def find_work_directory(filename):
    global WORKDIRS

    workdir = None
    FILESIZE = os.path.getsize(filename) / 1024
    for entry in WORKDIRS:
        used, available = df(entry)
        if used != 'None':
            if long(available) > long(FILESIZE):
                workdir = entry
                break
    return workdir


if __name__ == "__main__":
    # Start of Script execution
    # Get the database settings
    # for line in open('/etc/mythtv/mysql.txt','r').readlines():
    #     splitline=line.strip().split('=')
    #     if splitline[0].lower() == 'dbhostname':
    #         DBHOST=splitline[1]
    #     if splitline[0].lower() == 'dbusername':
    #         DBUSER=splitline[1]
    #     if splitline[0].lower() == 'dbpassword':
    #         DBPASS=splitline[1]

    parser = argparse.ArgumentParser()
    db_group = parser.add_argument_group('Database Settings')
    db_group.add_argument(
        '--dbhostname', default='localhost', help='The hostname or ip address of the database server (%(default)s)'
    )
    db_group.add_argument(
        '--dbusername', default='mythtv', help='The database user to connect with (%(default)s)'
    )
    db_group.add_argument(
        '--dbpassword', default='mythtv', help='The database password for the user (%(default)s)'
    )
    parser.add_argument(
        'filename', help='Name of file to transcode'
    )
    parser.add_argument(
        '--cutcommercials', action="store_true",
        help='Cut the commercials out of the video, this automatically enables the transcode option'
    )
    parser.add_argument(
        '--cropvideo', action="store_true", help="Crop the black borders off the sides of the video"
    )
    parser.add_argument(
        '--croptwice', action='store_true',
        help='Crop a second time after removing the horizcrop/horizcropprecent and cutting out commercials'
    )
    parser.add_argument(
        '--examineframes', type=int, default=0,
        help='The number of frames to examine to determine the crop amount, the default is all frames'
    )
    parser.add_argument(
        '--horizcrop', type=int, default=1,
        help='Additional number of horizontal lines to crop from the top and the bottom'
    )
    parser.add_argument(
        '--horizcroppercent', type=int, default=0,
        help='Percentage of lines to crop from top and bottom, overrides horizcrop (useful for removing garbage lines '
             'from the top of some recordings'
    )
    parser.add_argument(
        '--allowrunagain', action='store_true',
        help='Run even if the video has been operated on before'
    )
    parser.add_argument(
        '--keeporiginal', action='store_true',
        help='Keeps the original files with a .old.x extension (can increase space usage significantly)'
    )
    parser.add_argument(
        '--transcode', action='store_true',
        help='Transcode the video'
    )
    parser.add_argument(
        '--deleteoldlocks', action='store_true',
        help='Delete old lock files with no associated video file'
    )
    parser.add_argument(
        '--deleteoldbackups', action='store_true',
        help='Delete old backup files'
    )
    parser.add_argument(
        '--runagain', action='store_true', help='Run operation on the file again'
    )
    args = parser.parse_args()
    logging.debug('command is: %s' % ' '.join(sys.argv))

    # This is needed because the video output by ffmpeg generates an
    # unable to initialize video error from the mythtv frontend until
    # it is ran through mythtranscode.
    if not args.cutcommercials:
        args.transcode = True

    if args.deleteoldlocks:
        deleteoldlocks()

    if args.deleteoldbackups:
        deleteoldbackups()

    #args.filename=args[0]
    BASENAME = os.path.basename(args.filename)
    if not os.path.exists(args.filename):
        fileexists = False
        for path in MYTHRECORDINGSPATH:
            if os.path.exists('%s/%s' % (path, BASENAME)):
                fileexists = True
                DIRNAME = path
                args.filename = '%s/%s' % (path, BASENAME)
                break
        if not fileexists:
            print 'No such file, %s' % args.filename
            sys.exit(5)

    workdir = find_work_directory(args.filename)
    logging.debug('Work Directory: %s', workdir)

    # Create a video object
    vid = video(
        filename=args.filename, workdir=workdir, dbhost=args.dbhostname, dbuser=args.dbusername, dbpass=args.dbpassword
    )

    logging.debug('Checking for lock file')
    if not args.runagain:
        if vid.checklockfile():
            print 'cleanupvideo.py has already been run on this file'
            sys.exit(1)
        else:
            print('cleanvideo.py is currently running on this file or exited abnormally')
            print('check file and rerun with --runagain if the previous run failed')
            sys.exit(1)

    logging.debug('Creating the lock file')
    vid.createlockfile(completed=False)
    if args.cropvideo:
        logging.debug(
            'Detecting Video cropborders with horizcrop=%d, horizcroppercent=%d' % (
                args.horizcrop, args.horizcroppercent
            )
        )
        vid.detectcropvalues(frames=EXAMINEFRAMES, horizcrop=args.horizcrop, horizcroppercent=args.horizcroppercent)
        logging.debug('Cropping the video')
        if not vid.crop(keeporiginal=args.keeporiginal):
            vid.deletelockfile()
            print 'ERROR: All cropping options failed, exiting without making any changes'
            sys.exit(9)

    if args.cutcommercials:
        logging.info('Removing commercials')
        vid.cutcommercials(keeporiginal=args.keeporiginal)

    if args.croptwice:
        logging.debug('Detecting crop boundries a second time')
        vid.detectcropvalues(frames=args.examineframes, horizcrop=0, horizcroppercent=0)
        logging.debug('Cropping the video a second time')
        vid.crop(keeporiginal=args.keeporiginal)


    # If the video has not been transcoded and the transcode option is enabled, transcode the video
    if not args.cutcommercials and args.transcode:
        vid.transcode(keeporiginal=args.keeporiginal)

    logging.debug('Updating the seeklist')
    vid.rebuildseeklist()

    logging.debug('Updating the lock file to indicate cleanvideo ran sucessfully')
    vid.marktranscoded()
    vid.createlockfile(completed=True)
