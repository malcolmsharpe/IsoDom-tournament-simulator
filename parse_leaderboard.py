import os.path
from paths import boardtxt
import re
import sys

if len(sys.argv) < 2:
  print 'Usage: python parse_leaderboard.py leaderboard.YYYYMMDD.html ...'
  sys.exit(1)

for path in sys.argv[1:]:
  print 'Parsing leaderboard "%s"...' % path

  m = re.search(r'\.([0-9]{8})\.', path)
  assert m
  date_string = m.group(1)

  def parse_leaderboard(path):
    f = file(path)

    for line in f:
      m = re.search(r'<td>([-0-9\.]*) &plusmn; ([0-9.]*)</td><td class=c2>([0-9]*)</td>'
                    r'<td class=c>([0-9]*)</td><td>([^<]*) <',
                    line)
      if m:
        mean_skill = float(m.group(1))
        uncertainty = float(m.group(2))
        rank = int(m.group(3))
        games = int(m.group(4))
        name = m.group(5)

        yield (mean_skill, uncertainty, rank, games, name)

  f = file(os.path.join(boardtxt, 'leaderboard.%s.txt' % date_string), 'w')
  for record in parse_leaderboard(path):
    print >>f, repr(record)
