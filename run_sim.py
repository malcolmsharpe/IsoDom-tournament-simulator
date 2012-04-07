import cProfile
import math
import os
import os.path
from paths import boardtxt
import re
import scipy
from scipy.stats import norm
import sys

def main():
  if len(sys.argv) < 2:
    print 'Usage: python run_sim.py trials [weekN.txt ...]'
    sys.exit(1)
  trials = int(sys.argv[1])
  weeks = sys.argv[2:]

  std_norm = norm(0,1)

  # TrueSkill parameters, from the Isotropic Dominion FAQ:
  #   http://dominion.isotropic.org/faq/#leaderboard
  beta = 25.0
  draw_prob = 0.05

  # Calculate the draw margin eps.
  eps = math.sqrt(2) * beta * std_norm.ppf((draw_prob+1.0)/2.0)

  # Read groupings.
  kirian = []
  mustard = []
  brackets = [kirian, mustard]

  target_bracket = None
  current_group = {}
  for line in file('data/grouping.txt'):
    if "Kirian's Bracket:" in line:
      target_bracket = kirian
    elif "Mustard's Bracket:" in line:
      target_bracket = mustard
    else:
      line = line.strip()
      if line:
        handle = line.split(' -')[0].strip()
        current_group[handle] = None

        if len(current_group) == 8:
          target_bracket.append(current_group)
          current_group = {}

  assert len(current_group) == 0

  # Read leaderboard data.
  class Player(object):
    def __init__(self, line=None, name=None):
      if line is not None:
        assert name is None
        (self.mean_skill,
         self.uncertainty,
         self.rank,
         self.games,
         self.name) = eval(line)
      else:
        assert name is not None
        # This player isn't on the leaderboard, so we use default values.
        # The predictions for this player won't be very good.
        self.mean_skill = 25.0
        self.uncertainty = 25.0
        self.rank = None
        self.games = 0
        self.name = name

      # The uncertainty showed on the leaderboard is
      #   3 * (standard deviation of skill).
      self.sigma = self.uncertainty/3.0
      self.skill_distr = norm(self.mean_skill, self.sigma)

    def preinit(self):
      # Run once before a batch of simulations.
      self.group_wins = 0
      self.alltime_points = 0

    def init(self):
      # Run before a single simulation run.
      # Skill is determined at the beginning of simulation.
      # This accounts for the dark horse effect.
      self.skill = self.skill_distr.rvs()
      self.points = 0
      self.nplayed = 0

      # The distribution of performance.
      self._perf_rvs = []
      self.perf_distr = norm(self.skill, beta)

    def gen_perf(self):
      NRVS = 1000
      if not self._perf_rvs:
        self._perf_rvs = list(self.perf_distr.rvs(NRVS))
      return self._perf_rvs.pop()

    def incr_points(self, diff):
      self.points += diff
      self.alltime_points += diff

    def incr_nplayed(self, diff):
      self.nplayed += diff

    def __str__(self):
      return '%s (mu = %.1lf, sigma = %.1lf, s = %.1lf)' % (
        self.name, self.mean_skill, self.sigma, self.skill)

    def short_str(self):
      return '%s (mu = %.1lf, sigma = %.1lf)' % (
        self.name, self.mean_skill, self.sigma)

  # Read leaderboards starting with most recent.
  filenames = os.listdir(boardtxt)
  filenames.sort()
  filenames.reverse()

  first_board = True
  for fn in filenames:
    for line in file(os.path.join(boardtxt, fn)):
      p = Player(line=line)

      for b in brackets:
        for g in b:
          if p.name in g and g[p.name] is None:
            g[p.name] = p
            if not first_board:
              print 'WARNING: Using old entry for player "%s".' % p.name
    first_board = False

  # Print detailed brackets.
  if 0:
    print 'Brackets:'
    for b in brackets:
      print '  Groups:'
      for g in b:
        print '    Players:'
        for name,p in g.items():
          msg = ''
          if p is None:
            msg = ' MISSING!'
          print '      %s%s' % (name,msg)
        print

  # Fill in missing players with default entries.
  for b in brackets:
    for g in b:
      for name in g:
        if g[name] is None:
          g[name] = Player(name=name)
          print 'WARNING: Added default entry for player "%s".' % name

  # Collect all players.
  players = []
  for b in brackets:
    for g in b:
      players.extend(g.values())

  name_to_player = {}
  for p in players:
    name_to_player[p.name] = p

  print

  # Read weeks.
  preplayed = {}
  for week in weeks:
    for line in file(week):
      if 'vs.' not in line: continue
      m = re.match(r'(.*) vs\. (.*) ([0-9]+)-([0-9]+)-([0-9]+)', line)

      if m is None:
        print 'WARNING: "%s" parse failed on line "%s"' % (week, line.strip())
        continue

      p1name, p2name = m.group(1), m.group(2)
      w, l, t = map(int, [m.group(3), m.group(4), m.group(5)])

      ok = True
      for name in [p1name, p2name]:
        if name not in name_to_player:
          print 'WARNING: "%s" had unknown player "%s"' % (week, name)
          ok = False
      if not ok:
        continue

      if not p1name < p2name:
        tmp = p1name
        p1name = p2name
        p2name = tmp

        tmp = w
        w = l
        l = tmp

      preplayed[p1name, p2name] = (w, l, t)

    print
      

  # Run simulation.
  def run_simulation(verbose=False):
    def play_match(p1, p2):
      t1 = p1.gen_perf()
      t2 = p2.gen_perf()

      if verbose:
        print 'Players "%s" and "%s" playing a match.' % (p1.name, p2.name)
        print '  "%s" performance: %.1lf' % (p1.name, t1)
        print '  "%s" performance: %.1lf' % (p2.name, t2)

      diff = t1 - t2

      if diff > eps:
        if verbose:
          print '  "%s" wins!' % p1.name
          print
        return 2,0
      elif diff < -eps:
        if verbose:
          print '  "%s" wins!' % p2.name
          print
        return 0,2
      else:
        if verbose:
          print '  "%s" and "%s" rejoice in their shared victory!' % (
            p1.name, p2.name)
          print
        # Tie.
        return 1,1

    SERIES_LENGTH = 7
    def play_series(p1, p2):
      if verbose:
        print '*** Players "%s" and "%s" playing a 7-game series.' % (
          p1.name, p2.name)

      for i in range(SERIES_LENGTH):
        pts1, pts2 = play_match(p1, p2)
        p1.incr_points(pts1)
        p1.incr_nplayed(1)
        p2.incr_points(pts2)
        p2.incr_nplayed(1)

    def record_series(p1, p2, w, l, t):
      if verbose:
        print '*** Players "%s" and "%s" recorded a 7-game series.' % (
          p1.name, p2.name)

      assert w+l+t == SERIES_LENGTH

      p1.incr_points(2*w+t)
      p1.incr_nplayed(SERIES_LENGTH)
      p2.incr_points(2*l+t)
      p2.incr_nplayed(SERIES_LENGTH)

    def play_tiebreaker(p1, p2):
      if verbose:
        print '*** Players "%s" and "%s" playing tiebreaker series.' % (
          p1.name, p2.name)
      
      WIN_THRESHOLD = 4
      p1.wins = 0
      p2.wins = 0
      while 1:
        if p1.wins >= WIN_THRESHOLD:
          return p1
        if p2.wins >= WIN_THRESHOLD:
          return p2

        pts1, pts2 = play_match(p1, p2)
        if pts1 == 2: p1.wins += 1
        if pts2 == 2: p2.wins += 1

    # Initialize simulation.
    if verbose:
      print '*** Initializing simulation.'
    for p in players:
      p.init()
      if verbose:
        print '"%s" skill: %.1lf' % (p.name, p.skill)
    if verbose:
      print

    # Record pre-played games.
    for (p1name, p2name), (w,l,t) in preplayed.items():
      assert p1name < p2name
      record_series(name_to_player[p1name], name_to_player[p2name], w, l, t)

    if verbose:
      print '*** Pre-played standings:'
      print '      PPG PTS GMS NAME'
      print 'Brackets:'
      for b in brackets:
        print '  Groups:'
        for g in b:
          print '    Ranking:'
          ranking = sorted(g.values(), key=lambda p: -p.points/float(p.nplayed))
          for p in ranking:
            pts = p.points
            games = p.nplayed
            pts_per_game = pts / float(games)
            print '      %3.1lf %3d %3d %s' % (pts_per_game, pts, games, p.name)
          print
      print

    # Play standard games.
    for b in brackets:
      for g in b:
        for p1 in g.values():
          for p2 in g.values():
            # Want every unordered pair just once.
            if p1.name < p2.name and (p1.name, p2.name) not in preplayed:
              play_series(p1, p2)

    # Determine winners (possibly involving tie-breaking series).
    bracket_winners = []
    for b in brackets:
      group_winners = []
      for g in b:
        max_points = max(p.points for p in g.values())
        leaders = [p for p in g.values() if p.points == max_points]

        if len(leaders) > 1:
          if len(leaders) > 2:
            print 'WARNING: More than two group winners: %s' % leaders
          leaders = [play_tiebreaker(leaders[0], leaders[1])]
        leader, = leaders
        leader.group_wins += 1
        group_winners.append(leader)
      bracket_winners.append(group_winners)

    # Report detailed results.
    if verbose:
      print 'Brackets:'
      for b in brackets:
        print '  Groups:'
        for g in b:
          print '    Ranking:'
          ranking = sorted(g.values(), key=lambda p: -p.points)
          for p in ranking:
            print '      %2d: %s' % (p.points, p)
          print

    # Report winners.
    if verbose:
      print 'Bracket winners:'
      for gw in bracket_winners:
        print '  Group winners:'
        for p in gw:
          print '    %s' % p
        print

  for p in players:
    p.preinit()

  INCR = 10
  for trial in range(trials):
    if trial%INCR == 0:
      print 'Run %3d of %3d trials.' % (trial, trials)
    verbose = (trials == 1)
    run_simulation(verbose=verbose)
  print

  if trials > 1:
    # Print players.
    for p in players:
      print p.short_str()
    print

    # Report results.
    print 'Brackets:'
    for b in brackets:
      print '  Groups:'
      for g in b:
        print '    Ranking:'
        ranking = sorted(g.values(), key=lambda p: -p.group_wins)
        for p in ranking:
          win_pct = 100.0 * p.group_wins / float(trials)
          avg_pts = p.alltime_points / float(trials)
          print '      %2.0lf%% (avg pts %2d): %s' % (
            win_pct, avg_pts, p.name)
        print

main()
#cProfile.run('main()')
