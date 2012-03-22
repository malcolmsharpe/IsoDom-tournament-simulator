from datetime import datetime
import os
import os.path
from paths import tmpdir, boardhtml
import re

def detect_date(path):
  for line in file(path):
    m = re.search('class=date>generated ([^>]*)<', line)
    
    if m is not None:
      in_fmt = '%a %b %d %H:%M:%S %Y'
      dt = datetime.strptime(m.group(1), in_fmt)
      out_fmt = '%Y%m%d'
      return dt.strftime(out_fmt)
    
  assert 0


def download(url):
  print 'Downloading from "%s"...' % url

  target = os.path.join(tmpdir, 'leaderboard.html')
  os.system('wget -O %s %s' % (target, url))
  date_string = detect_date(target)
  print '  Date: %s' % date_string

  final = os.path.join(boardhtml, 'leaderboard.%s.html' % date_string)

  os.system('mv %s %s' % (target, final))


board_url = 'dominion.isotropic.org/leaderboard/'

# Most recent board with rspeer present.
rspeer_url = 'http://bggdl.square7.ch/leaderboard/leaderboard-2012-03-12.html'

# Most recent board with Tonks77 present.
tonks77_url = 'http://bggdl.square7.ch/leaderboard/leaderboard-2012-03-20.html'


download(board_url)
download(rspeer_url)
download(tonks77_url)
