#!/usr/bin/python
import os
import sys
import tempfile
import getopt
import re
import socket
import logging
import argparse
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
HORIZCROP=1
HORIZCROPPERCENT=0
DBHOST='localhost'
DBUSER='mythtv'
DBPASS='mythtv'
CUTCOMMERCIALS=False
CROPVIDEO=False
CROPTWICE=False
TRANSCODE=False
RUNAGAIN=False
KEEPORIGINAL=False
EXAMINEFRAMES=0
TURBO=213
MPEGQUALITY=1800
MYTHRECORDINGSPATH=['/var/lib/mythtv/recordings', '/usr/local/mythtv/recordings', '.']

# WORKDIRS is A list of directories we can use for temporary files, we will check if the directory exists and has
# adequate space and use the first directory from the list with enough room.
WORKDIRS=['/tmp','/work','/var/lib/mythtv/recordings','/usr/local/mythtv/recordings']
WORKDIR='/var/lib/mythtv/recordings'

    
class video:
    def __init__(self,filename='', workdir=WORKDIR, logfile='/tmp/cleanupvideo.out'):
        self.filename=filename
        self.width=0
        self.height=0
        self.framerate=0
        self.currentcrop=''
        self.frames=0
        self.horizcrop=HORIZCROP
        self.horizcroppercent=HORIZCROPPERCENT
        self.croptop=0
        self.cropleft=0
        self.cropright=0
        self.cropbottom=0
        self.operationnumber=0
        self.logfile=logfile
        self.workdir=workdir

    def detectcropvalues(self, frames=0, horizcrop=-1, horizcroppercent=-1, turbo=TURBO):
        segmentsecs=5
        if turbo < segmentsecs:
            turbo=segmentsecs*2
        if horizcrop != -1:
            # This value is the number of 16 line blocks to crop from the top/bottom, so we need to multiply by 16
            self.horizcrop=int(horizcrop)*16
        if horizcroppercent != -1:
            self.horizcroppercent=horizcroppercent
        if frames != 0:
            self.frames=frames
        cropsizes={}
        crop=''
        WIDTH=0
        HEIGHT=0
        edlfilename='%s/cleanvideo_tmp.edl' % self.workdir
        edifilename=tempfile.mktemp('.edl','cleanupvideo_',self.workdir)
        fh=open(edifilename,'w')
        for sec in range(1,14000,turbo):
            fh.write('%d %d 0\n' % (sec,sec+(turbo-segmentsecs)))
        fh.close()
        if frames == 0:
            command='mplayer -quiet -edl %s -benchmark -nosound -vf cropdetect=24:16 -vo null %s 2> /dev/null' % (edifilename,self.filename)
        else:
            command='mplayer -quiet -edl %s -benchmark -nosound -vf cropdetect=24:16 -frames %d -vo null %s 2>/dev/null' % (edifilename,frames,self.filename)
        logging.debug('Running command:',command)
        for line in os.popen(command).readlines():
            splitline=line.strip().split()
            if len(splitline) > 3 and splitline[0] == 'VIDEO:':
                WIDTH=splitline[2].split('x')[0]
                HEIGHT=splitline[2].split('x')[1]
                self.framerate=splitline[5]
            if len(splitline) > 7 and splitline[0] == '[CROP]':
                crop=splitline[8][5:-2]
            try:
                cropsizes[crop]=cropsizes[crop]+1
            except KeyError:
                cropsizes[crop]=1
        currentcropcount=0
        currentcrop=''
        for crop in cropsizes.keys():
            if cropsizes[crop] > currentcropcount:
                currentcrop=crop
                currentcropcount=cropsizes[crop]
        if len(currentcrop):
            splitcrop=currentcrop.split(':')
            height=int(splitcrop[1])
            evenheight=(height/16)*16
            remainder=height-evenheight
            if horizcroppercent > 0:
                horizcrop=int(float(height)*(float(horizcroppercent)*.01))
            if remainder == horizcrop:
                currentcrop='%d:%d:%d:%d' % (int(splitcrop[0]),int(splitcrop[1])-(horizcrop/2),int(splitcrop[2]),int(splitcrop[3])+(horizcrop/2))
            if remainder > horizcrop:
                currentcrop='%d:%d:%d:%d' % (int(splitcrop[0]),int(splitcrop[1])-(remainder/2),int(splitcrop[2]),int(splitcrop[3])+(remainder/2))
            if remainder < horizcrop:
                currentcrop='%d:%d:%d:%d' % (int(splitcrop[0]),evenheight-16,int(splitcrop[2]),int(splitcrop[3])+8)
        self.width=int(WIDTH)
        self.height=int(HEIGHT)
        self.currentcrop=currentcrop
        if len(currentcrop):
            cropvalues=currentcrop.split(':')
            self.croptop=int(cropvalues[3])
            self.cropleft=int(cropvalues[2])
            self.cropright=self.width-(self.cropleft+int(cropvalues[0]))
            self.cropbottom=self.height-(self.croptop+(int(cropvalues[1])))
            if self.cropbottom < 0:
                self.cropbottom=0
        logging.debug(
            'Crop borders are', self.width,self.height,self.croptop, self.cropleft, self.cropbottom, self.cropright)
        os.remove(edifilename)

    def createlockfile(self, completed=False):
        fh=open("%s.cleanupvideoran" % self.filename,'w')
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
        rc=9
        try:
            fh=open("%s.cleanupvideoran" % self.filename, 'r')
        except IOError:
            return(2)
        for line in fh.readlines():
            if len(line):
                splitline=line.strip().split()
                if splitline[0] == 'completed:':
                    try:
                        rc=int(splitline[1])
                    except ValueError:
                        if splitline[1] == 'True':
                            rc=1
                        else:
                            rc=0
        return(rc)

    def swapfiles(self, keeporiginal=False):
        logging.debug('Swapping files: %s/new.%s <-> %s' % (self.workdir,os.path.basename(self.filename),self.filename))
        if keeporiginal:
            for backupnumber in range(self.operationnumber, 999):
                try:
                  fh=open('%s/%s.%d' % (self.workdir,os.path.basename(self.filename), backupnumber))
                  fh.close()
                except IOError:
                  break
            try:
                fh=open('%s/new.%s' % (self.workdir,os.path.basename(self.filename)))
            except IOError:
                print 'New file did not get created'
                return(1)
            fh.close()
            os.rename(self.filename,'%s.old.%d' % (self.filename, backupnumber))
            # This doesn't work if the files aren't on the same device
            #os.rename('%s/new.%s' % (self.workdir,os.path.basename(self.filename),self.filename))
            os.system('mv %s/new.%s %s' % (self.workdir,os.path.basename(self.filename),self.filename))
        else:
            try:
                fh=open('%s/new.%s' % (self.workdir,os.path.basename(self.filename)))
            except IOError:
                print 'New file did not get created'
                return(1)
            fh.close()
            os.remove(self.filename)
            # This doesn't work if both files aren't on the same filesystem
            #os.rename('%s/new.%s' % (self.workdir,os.path.basename(self.filename)), self.filename)
            os.system('mv %s/new.%s %s' % (self.workdir,os.path.basename(self.filename),self.filename))
        self.operationnumber=self.operationnumber+1
        return(0)
    def crop(self, keeporiginal=False, format='mp4', resize=False, mpegquality=MPEGQUALITY):  
        if self.currentcrop=='':
            logging.debug('No crop boundries for this video object, running cropdetect')
            vid.detectcropvalues()
        if self.croptop == 0 and self.cropbottom == 0 and self.cropleft == 0 and self.cropright == 0:
            print 'No crop borders detected'
            return(0)
        # I am overriding the framerate here since it doesn't always get the correct framerate??
        vid.framerate=29.97
        # Try it first just cropping, if it doesn't work try specifying the target format
        logging.debug(
            'Running command: ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -aspect 16:9 -f mp4 -b %dkb "%s/new.%s"' % (self.logfile,self.filename,self.cropleft,self.cropright,self.croptop,self.cropbottom,mpegquality,self.workdir,os.path.basename(self.filename)))
        rc=os.system('ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -aspect 16:9 -f mp4 -b %dkb "%s/new.%s"' % (self.logfile, self.filename,self.cropleft,self.cropright,self.croptop,self.cropbottom,mpegquality,self.workdir,os.path.basename(self.filename)))>>8
        if rc == 1:
            logging.debug('Running command: ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -target ntsc-dvd -aspect 16:9 -b %dkb "%s/new.%s"' % (self.logfile,self.filename,self.cropleft,self.cropright,self.croptop,self.cropbottom,mpegquality,self.workdir,os.path.basename(self.filename)))
            rc=os.system('ffmpeg >> %s 2>&1 -y -i "%s" -cropleft %d -cropright %d -croptop %d -cropbottom %d -target ntsc-dvd -aspect 16:9 -b %dkb "%s/new.%s"' % (self.logfile,self.filename,self.cropleft,self.cropright,self.croptop,self.cropbottom,mpegquality,self.workdir,os.path.basename(self.filename)))>>8
            if rc == 1:
                logging.debug('Crop failed, returning failure code')
                return False
        self.swapfiles(keeporiginal)
        return True

    def cutcommercials(self, keeporiginal=False):
    # Commercial cutting is experimental and may not work as intended
        rc=os.system('mythcommflag > /dev/null 2>&1 -f %s' % self.filename) >> 8
        if rc > 126:
            print 'Commercial flagging failed for filename %s with error %d' % (self.filename,rc)
            return(1)
        rc=os.system('mythcommflag --gencutlist -f %s' % self.filename) >> 8
        if rc != 0:
            print 'Copying cutlist failed for %s with error %d' % (self.filename,rc)
            return(1)
        temppath=''
        rc=os.system('mythtranscode --honorcutlist -i "%s" -o "%s/new.%s"' % (self.filename,self.workdir,os.path.basename(self.filename))) >> 8
        if rc != 0:
            print 'Cut commercials and transcoding failed for %s with error %d' % (self.filename,rc)
            return(2)
        self.swapfiles(keeporiginal)
        self.clearcutlist()

    def transcode(self, keeporiginal=False):
        rc=os.system('mythtranscode -i "%s" -o "%s/new.%s"' % (self.filename, self.workdir,os.path.basename(self.filename))) >> 8
        if rc != 0:
            print 'Transcoding failed for %s with error %d' % (self.filename, rc)
            return(2)
        self.swapfiles(keeporiginal)
        self.clearcutlist()

    def rebuildseeklist(self):
        rc=os.system('mythcommflag --video %s' % self.filename) >> 8
        if rc != 0:
            print 'Rebuilding seek list failed for %s with error %d' % (self.filename,rc)
            return(1)

    def clearcutlist(self):
        rc=os.system('mythcommflag --clearcutlist -f %s' % self.filename) >> 8
        conn = MySQLdb.connect (host = DBHOST, user = DBUSER, passwd = DBPASS, db = "mythconverg")
        cursor = conn.cursor()
        cursor.execute("UPDATE recorded SET cutlist=0,filesize=%ld WHERE basename='%s';" % (os.path.getsize(self.filename),os.path.basename(self.filename)))
        cursor.close()
        conn.close() 
        if rc != 0 :
            print 'Clearing cutlist failed for %s with error %d' % (self.filename,rc)
            return(1)

    def marktranscoded(self):
        conn=MySQLdb.connect(host = DBHOST, user=DBUSER, passwd=DBPASS, db="mythconverg")
        cursor=conn.cursor()
        cursor.execute("update recorded set transcoded=1 where basename='%s';" % (os.path.basename(self.filename)))
        cursor.close()
        conn.close()


def deleteoldlocks(path=MYTHRECORDINGSPATH):
    if len(path) == 0:
        return
    for directory in path:
        try:
            files=os.listdir(directory)
            for file in files:
                if re.search('cleanupvideoran$', file) != None:
                    tempfile='.'.join(file.split('.')[:-1])
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
            files=os.listdir(directory)
            for file in files:
                if re.search('\.old\.*', file) != None:
                    tempfile='.'.join(file.split('.')[:-2])
                    if tempfile not in files:
                        logging.debug('DEBUG: Deleting old backup file: %s' % os.path.join(directory, file))
                        os.remove(os.path.join(directory, file))
        except OSError:
            pass


def df(directory='/', humanreadable=False):
    if humanreadable == True:
        options='-khP'
    else:
        options='-kP'
    try:
        dfout=os.popen('df %s %s 2>/dev/null' % (options,directory)).readlines()[1]
    except IndexError:
        return 'None','None'
    splitline=dfout.split()
    return splitline[2],splitline[3]

def usage():
    print 'Usage: cleanvideo [--cutcommercials] [--transcode] [--cropvideo] [--croptwice] [--examineframes numframes] [--horizcrop numlines] [--horizcroppercent percent] [--allowrunagain] [--keeporiginal] FILENAME'
    print '\t--cutcommercials\tCut the commercials out of the video, this automatically enables the transcode option'
    print '\t--cropvideo     \tCrop the black borders off the sides of the video'
    print '\t--croptwice     \tCrop a second time after removing the horizcrop/horizcropprecent and cutting out commercials'
    print '\t--transcode     \tTranscode the video'
    print '\t--examineframes \tThe number of frames to examine to determine the crop amount, the default is all frames'
    print '\t--horizcrop     \tAdditional number of horizontal lines to crop from the top and the bottom'
    print '\t--horizcropprecent\tPercentage of lines to crop from top and bottom, overrides horizcrop'
    print '\t                \t(useful for removing garbage lines from the top of some recordings)'
    print '\t--allowrunagain \tRun even if it has been run before'
    print '\t--keeporiginal  \tKeeps the original files with a .old.x extension (can increase space usage significantly)'
    print '\t--deleteoldlocks\tDelete old lock files with no associated video file'
    print '\t--deleteoldbackups\tDelete old backup files'
    print
    print 'Notes:'
    print '\tCutting commercials always uses mythtranscode which also'
    print '\ttranscodes the video with the settings defined for the'
    print '\trecording in mythtv.'
    print '\tCropping always transcodes to MP4 file with the borders'
    print '\tcropped and other video settings as close to the original'
    print '\tfile as possible.'


if __name__ == "__main__":
    # Start of Script execution
    # Get the database settings
    for line in open('/etc/mythtv/mysql.txt','r').readlines():
        splitline=line.strip().split('=')
        if splitline[0].lower() == 'dbhostname':
            DBHOST=splitline[1]
        if splitline[0].lower() == 'dbusername':
            DBUSER=splitline[1]
        if splitline[0].lower() == 'dbpassword':
            DBPASS=splitline[1]

    parser = argparse.ArgumentParser()
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
    args = parser.parse_args()
    logging.debug('command is: %s' % ' '.join(sys.argv))
    # Parse the command line
    try:
        opts,args = getopt.getopt(sys.argv[1:],"h",["cutcommercials","cropvideo","croptwice","allowrunagain","examineframes=","horizcrop=","horizcroppercent=","keeporiginal","deleteoldlocks","deleteoldbackups","transcode","help"])
    except getopt.GetoptError:
        usage()
        sys.exit(2)
    for o,a in opts:
        #if o in ("-h","--help"):
        #  usage()
        #  sys.exit(0)
        #if o in ("--cutcommercials"):
        #  CUTCOMMERCIALS=True
        #if o in ("--cropvideo"):
        #    CROPVIDEO=True
        #if o in ("--croptwice"):
        #    CROPTWICE=True
        #    CROPVIDEO=True
        #if o in ("--examineframes"):
        #    EXAMINEFRAMES=a
        #if o in ("--horizcrop"):
        #    HORIZCROP=a
        #if o in ("--horizcroppercent"):
        #    HORIZCROPPERCENT=a
        #if o in ("--allowrunagain"):
        #    RUNAGAIN=True
        #if o in ("--keeporiginal"):
        #    KEEPORIGINAL=True
        #if o in ("--transcode"):
        #    TRANSCODE=True
        if o in ("--deleteoldlocks"):
            deleteoldlocks()
        if o in ("--deleteoldbackups"):
            deleteoldbackups()
    if len(args) != 1:
      print 'To many arguments'
      usage()
      sys.exit(1)

    # This is needed because the video output by ffmpeg generates an
    # unable to initialize video error from the mythtv frontend until
    # it is ran through mythtranscode.
    if CUTCOMMERCIALS == False:
        TRANSCODE=True

    FILENAME=args[0]
    BASENAME=os.path.basename(FILENAME)
    if os.path.exists(FILENAME) == False:
        fileexists=False
        for path in MYTHRECORDINGSPATH:
            if os.path.exists('%s/%s' % (path,BASENAME)):
                fileexists=True
                DIRNAME=path
                FILENAME='%s/%s' % (path,BASENAME)
                break
        if fileexists == False:
            print 'No such file, %s' % FILENAME
            sys.exit(5)
    FILESIZE=os.path.getsize(FILENAME)/1024
    for entry in WORKDIRS:
        used,available=df(entry)
        if used != 'None':
            if long(available) > long(FILESIZE):
                WORKDIR=entry
                break

    logging.debug('Work Directory:',WORKDIR)

    # Create a video object
    vid=video(filename=FILENAME,workdir=WORKDIR)

    logging.debug('DEBUG: Checking for lock file')
    if RUNAGAIN == False:
        if vid.checklockfile() == True:
            print 'cleanupvideo.py has already been run on this file'
            sys.exit(1)
        if vid.checklockfile() == False:
            print 'cleanvideo.py is currently running on this file or exited abnormally'
            print 'check file and rerun with --runagain if the previous run failed'
            sys.exit(1)

    logging.debug('Creating the lock file')
    vid.createlockfile(completed=False)

    if CROPVIDEO:
        logging.debug('Detecting Video cropborders with horizcrop=%d, horizcroppercent=%d' % (HORIZCROP, HORIZCROPPERCENT))
        vid.detectcropvalues(frames=EXAMINEFRAMES, horizcrop=HORIZCROP, horizcroppercent=HORIZCROPPERCENT)
        logging.debug('Cropping the video')
        if vid.crop(keeporiginal=KEEPORIGINAL)==False:
            vid.deletelockfile()
            print 'ERROR: All cropping options failed, exiting without making any changes'
            sys.exit(9)

    if CUTCOMMERCIALS:
        logging.info('Removing commercials')
        vid.cutcommercials(keeporiginal=KEEPORIGINAL)

    if CROPTWICE:
        logging.debug('Detecting crop boundries a second time')
        vid.detectcropvalues(frames=EXAMINEFRAMES, horizcrop=0, horizcroppercent=0)
        logging.debug('Cropping the video a second time')
        vid.crop(keeporiginal=KEEPORIGINAL)

    # If the video has not been transcoded and the transcode option is enabled, transcode the video
    if CUTCOMMERCIALS == False and TRANSCODE == True:
        vid.transcode(keeporiginal=KEEPORIGINAL)

    logging.debug('Updating the seeklist')
    vid.rebuildseeklist()

    logging.debug('Updating the lock file to indicate cleanvideo ran sucessfully')
    vid.marktranscoded()
    vid.createlockfile(completed=True)
