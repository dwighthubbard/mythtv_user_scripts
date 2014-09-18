#!/usr/bin/python
import  os,sys,tempfile,getopt,urllib
try:
    import MySQLdb
except ImportError:
    print 'This program requires the python MySQLdb module'
    sys.exit(10)
    
# Set up the variables
# intialize variables
DB='mythconverg'
USER='root'
OUTPATH='/tmp'
COVERPATH='/var/lib/mythtv/posters'
FRAME='00000001.jpg'
SKIPPERCENT=4
UPDATEMISSINGIMDB=False
UPDATEMISSINGCOVER=False
UPDATENOIMDBCOVER=False
COVERFORMAT='single'

# These are external binaries we need
BINARIES=['rm','mv','chown','montage','mplayer','ffmpeg']

def usage():
    print 'Usage: createvideoposters --updatemissingimdb|--updatemissingcover|--updatenoimdbcover [--single|--montage] [--offset] --[help]'
    
def getcoverdir():
    # Connect to the database and get the path to the COVER directory
    HOSTNAME='localhost'
    HOSTNAME=os.popen('uname -n').readlines()[0].strip()
    conn = MySQLdb.connect (host = DB, user = USER, passwd = DBPASS, db = "mythconverg")
    cursor = conn.cursor()
    rows=[]
    if cursor.execute("select data from settings where value = 'VideoArtworkDir' and hostname = '%s';" % HOSTNAME ):
        rows=cursor.fetchall()
    conn.close()
    COVERPATH=(rows[0])[0]
    return COVERPATH

#+-------+-----------+---------------+-------+---------+----------+------+------------+--------+-----------+------------------+----------------------------------------------+----------+---------+-------------------+----------+
#| intid | title      | director    | plot | rating| inetref  |year|userrating|length|showlevel| filename   | coverfile                                  | childid|browse|playcommand|category|
#+-------+-----------+---------------+-------+---------+----------+------+------------+--------+-----------+------------------+----------------------------------------------+----------+---------+-------------------+----------+
def getvideoswithoutcoverimage():
    conn = MySQLdb.connect (host = DB, user = USER, passwd = DBPASS, db = "mythconverg")
    cursor = conn.cursor()
    rows=[]
    if cursor.execute(" select intid,filename from videometadata where coverfile='No Cover';" ):
        rows=cursor.fetchall()
    conn.close()
    return rows

def getvideoswithoutimdbnumber():
    conn = MySQLdb.connect (host = DB, user = USER, passwd = DBPASS, db = "mythconverg")
    cursor = conn.cursor()
    rows=[]
    if cursor.execute(" select intid,filename from videometadata where inetref=0;" ):
        rows=cursor.fetchall()
    conn.close()
    return rows

def getextension(filename):
    extension='none'
    extension=filename.split('.')[-1]
    return(extension)

def getmovielength(filename):
    for line in os.popen('(sleep 1;echo q)|mplayer 2> /dev/null -vo null -frames 100 -nosound -identify -vc null "%s"' % filename).readlines():
        if 'ID_LENGTH' in line.strip():
            return float(line.strip().split('=')[1])
    return -1

def reporthook(*a): 
  #print a
  pass
                    
def updatemissingimdb(excludedirectories=['/var/lib/exclude1','/var/lib/mythtv/exclude2']):
    print 'Error: This function is not complete and does not work'
    return
    for video in getvideoswithoutimdbnumber():
        skip=False
        for exclude in excludedirectories:
            if exclude in os.path.dirname(video[1]):
                skip=True
        if skip == False:
            print 'Video %s (%d) does not have an imdb number' % (video[1],video[0])
            videoname=os.path.basename(video[1].split('.')[0]).replace('_',' ').strip()
            print 'Searching IMDB for: %s' % videoname
            imdbinfo=os.popen('/usr/share/mythtv/mythvideo/scripts/imdb.pl -M "%s"' % videoname).readlines()
            if len(imdbinfo) == 0:
                print 'Trying again without a number at the end'
                imdbinfo=os.popen('/usr/share/mythtv/mythvideo/scripts/imdb.pl -M "%s"' % videoname.split('-')[0]).readlines()
            if len(imdbinfo):
                imdbnum=imdbinfo[0].split(':')[0].strip()
                print 'Video %s (%d) does not have an imdb number - Found: %s' % (video[1],video[0],imdbnum)
                videoinfo={}
                videoinfo['title']=videoname
                videoinfo['year']='unknown'
                videoinfo['director']='unknown'
                videoinfo['plot']=''
                videoinfo['userrating']=''
                videoinfo['coverfile']=''
                videoinfo['rating']=''
                videoinfo['length']='unknown'
                videoinfo['inetref']=imdbnum
                for line in os.popen('/usr/share/mythtv/mythvideo/scripts/imdb.pl -D %s' % imdbnum).readlines():
                    splitline=line.strip().split(':')
                    if len(splitline) > 1:
                        videoinfo[splitline[0].lower()]=splitline[1]
                posterurl=os.popen('/usr/share/mythtv/mythvideo/scripts/imdb.pl -P %s' % imdbnum).readlines()
                if len(posterurl):
                  print 'Poster is at:',posterurl[0].strip()
                  videoinfo['coverfile']='/var/lib/mythtv/posters/%s.jpg' % imdbnum
                urllib.urlretrieve(posterurl[0].strip(), '/var/lib/mythtv/posters/%s.jpg' % imdbnum, reporthook)
                conn = MySQLdb.connect (host = DB, user = USER, passwd = DBPASS, db = "mythconverg")
                cursor = conn.cursor()
                rows=[]
                if cursor.execute('update videometadata set title="%s", year="%s", director="%s", plot="%s", userrating="%s", coverfile="%s", rating="%s", length="%s", inetref="%s" where intid="%s";' % (videoinfo['title'],videoinfo['year'],videoinfo['director'],videoinfo['plot'],videoinfo['userrating'],videoinfo['coverfile'],videoinfo['rating'],videoinfo['length'],videoinfo['inetref'],imdbnum)):
                    rows=cursor.fetchall()
                conn.close()
    
def updatemissingcoverimage(format='single',location=SKIPPERCENT,all=False):
    tempdir=tempfile.mkdtemp()
    if all:
      list=getvideoswithoutimdbnumber()
    else:
      list=getvideoswithoutcoverimage()
    for video in list:
        movielen=getmovielength(video[1])
        print video[1],movielen
        if movielen != -1:
            offset=movielen*location/100
            if format == 'single':
                #os.system('mplayer >/dev/null 2>&1 -quiet -ss %s -vo jpeg:quality=60:outdir=%s -frames 2 -nosound "%s"' % (offset, tempdir, video[1]))
                #os.system('mplayer >/dev/null 2>&1 -quiet -ss %s -vo jpeg:quality=60:outdir=%s -frames 2 -nosound "%s"' % (offset, tempdir, video[1]))
                #os.system('mv "%s/00000002.jpg" "%s/intid.%d.jpg"' % (tempdir,COVERPATH, video[0]))
                os.system('ffmpeg > /dev/null 2>&1 -i "%s" -an -ss %s -vframes 1 %s/%%d.jpg' % (video[1],offset,tempdir))
                os.system('mv "%s/1.jpg" "%s/intid.%d.jpg"' % (tempdir,COVERPATH, video[0]))
            if format == 'montage':
                movielength=getmovielength(video[1])
                for location in [10,35,65,90]:
                    offset=movielength*location/100
                    print location,
                    #os.system('mplayer >/dev/null 2>&1 -quiet -ss %s -vo jpeg:quality=60:outdir=%s -frames 2 -nosound "%s"' % (offset, tempdir, video[1]))
                    #os.system('mplayer >/dev/null 2>&1 -quiet -vf framestep=%s -vo jpeg:quality=60:outdir=%s -frames 2 -nosound "%s"' % (offset, tempdir, video[1]))
                    #os.system('mv "%s/00000002.jpg" "%s/mosaic%2.2d.jpg"' % (tempdir,tempdir,location))
                    os.system('ffmpeg > /dev/null 2>&1 -i "%s" -an -ss %s -vframes 1 %s/%%d.jpg' % (video[1],offset,tempdir))
                    os.system('mv "%s/1.jpg" "%s/mosaic%2.2d.jpg"' % (tempdir,tempdir,location))
                os.system('montage -geometry +4+4 "%s/mosaic*.jpg" "%s/mosaic.jpg"' % (tempdir,tempdir))
                os.system('mv "%s/mosaic.jpg" "%s/intid.%d.jpg"' % (tempdir,COVERPATH,video[0]))
            #os.system('rm "%s/00000001.jpg" "%s/mosaic*.jpg"' % (tempdir,tempdir))
            #os.rmdir(tempdir) 
            os.system('chown mythtv "%s/intid.%d.jpg"' % (COVERPATH,video[0]))
            conn = MySQLdb.connect (host = DB, user = USER, passwd = DBPASS, db = "mythconverg")
            cursor = conn.cursor()
            rows=[]
            if cursor.execute("update videometadata set coverfile='%s/intid.%d.jpg' where intid=%d limit 1;" % (COVERPATH, video[0], video[0]) ):
                rows=cursor.fetchall()
            conn.close()
    try:
        os.remove('%s/00000001.jpg')
        os.rmdir(tempdir)
    except OSError:
        pass

# Parse the command line
try:
    opts,args = getopt.getopt(sys.argv[1:],"h",["updatenoimdbcover","updatemissingimdb","updatemissingcover","single","montage","offset=","help"])
except getopt.GetoptError:
    usage()
    sys.exit(2)
for o,a in opts:
    if o in ("-h","--help"):
      usage()
      sys.exit(0)
    if o in ("--updatemissingimdb"):
      UPDATEMISSINGIMDB=True
    if o in ("--updatemissingcover"):
        UPDATEMISSINGCOVER=True
    if o in ("--updatenoimdbcover"):
      UPDATENOIMDBCOVER=True
    if o in ('--single'):
        COVERFORMAT='single'
    if o in ('--montage'):
        COVERFORMAT='montage'
    if o in ('--offset'):
        OFFSET=a

if UPDATEMISSINGIMDB == False and UPDATEMISSINGCOVER == False and UPDATENOIMDBCOVER == False:
    usage()
    exit(0)
    
# We need to check for this actaully
print 'You must be running as the mythtvuser to run this'

# Get the information to log into mysql
for line in open('/etc/mythtv/mysql.txt','r').readlines():
    splitline=line.strip().split('=')
    if splitline[0].lower() == 'dbhostname':
        DB=splitline[1]
    if splitline[0].lower() == 'dbusername':
        USER=splitline[1]
    if splitline[0].lower() == 'dbpassword':
        DBPASS=splitline[1]

COVERPATH=getcoverdir()

if UPDATEMISSINGIMDB:
    updatemissingimdb()
if UPDATEMISSINGCOVER:
    print 'Creating %s images for recordings without covers' % COVERFORMAT
    updatemissingcoverimage(format=COVERFORMAT,all=False)
if UPDATENOIMDBCOVER:
    print 'Creating %s images for recordings without imdb entries' % COVERFORMAT
    updatemissingcoverimage(format=COVERFORMAT,all=True)
