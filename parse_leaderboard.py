import re
import sys

if len(sys.argv) != 2:
  print 'Usage: python parse_leaderboard.py leaderboard.html'
  sys.exit(1)

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

f = file('data/leaderboard.txt', 'w')
for record in parse_leaderboard(sys.argv[1]):
  print >>f, repr(record)
