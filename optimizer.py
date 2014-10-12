#!/usr/bin/python
#
# Copyright (c) 2011-2012, Peter Dornbach.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Modules to optimizes the purchase.
"""

import copy
import json
import math
import os
import os.path
import re
import sys
import subprocess
import unicodedata
import multiprocessing

import lfxml
import gflags
import item

FLAGS = gflags.FLAGS

gflags.DEFINE_string(
    'mode', 'builtin',
    '"builtin" runs the built in optimizer that works up to about '
    '--consider_shops=20. "gplk" will invoke the external glpsol '
    'linear program solver.')

gflags.DEFINE_boolean(
    'rerun_solver', False,
    'Force re-running the solver. Affects --mode=glpk only.')

gflags.DEFINE_integer(
    'multiple', 1,
    'Buys bricks for multiple sets, not just one.')

gflags.DEFINE_list(
    'include_shops', [],
    'Allows these shops only. If empty, all shops are allowed.')

gflags.DEFINE_list(
    'exclude_shops', [],
    'Does not allow these shops.')

gflags.DEFINE_list(
    'dont_exclude_shops', [],
    'Does allow these shops, even if excluded by country.')

gflags.DEFINE_list(
    'include_countries', [],
    'Allows these countries only. If empty, all countries are allowed.')

gflags.DEFINE_list(
    'exclude_countries', [],
    'Does not allow these countries.')

gflags.DEFINE_float(
    'shop_fix_cost', 5.0,
    'The overhead of adding one more shop, in local currency.')

gflags.DEFINE_integer(
    'max_shops', 8,
    'The maximum number of shops to evaluate for any possible combination of '
    'considered shops. Affects --mode=builtin only. Setting this to something '
    'smaller than consider_shops does not always speed up the time to '
    'solution, you will have to try with your specific query.')

gflags.DEFINE_integer(
    'consider_shops', 20,
    'Number of shops to consider. The optimizer will consider combinations of '
    'shops from a pool of this size. For mode=builtin the max feasible value '
    'is currently about 25 (depending on machine speed, parallelization, '
    'possibly the value of max_shops, and of course your patience. '
    'With mode=glpk it can be much more, about 60 or 100 may be still ok '
    'depending on the model.')
    
gflags.DEFINE_integer(
    'glpk_limit_seconds', 0,
    'If non-zero, glpk will spend so much time on finding the optimal '
    'solution.')

gflags.DEFINE_integer(
    'jobs', 8,
    'The maximum number of shops to evaluate for any possible combination of '
    'considered shops. Affects --mode=builtin only.',
    short_name = 'j', lower_bound = 1)

    

AMPL_MODEL="""
set Bricks;

set Shops;

# The demand for each brick.
param demand{b in Bricks}, integer;

# Unit price of each brick from shop s.
param unit_price{b in Bricks, s in Shops};

# Fix cost when ordering from shop s.
param fix_cost{s in Shops};

# Minimum order from each shop.
param min_order{s in Shops};

# Maximum total number of bricks to order from one shop. This can be
# arbitrarily high but is needed to enforce consistency
param max_bricks_from_shop;

# Do we order from shop s?
var order_shop{s in Shops}, binary >= 0;

# How many bricks we order of brick b from shop s?
var order_brick{b in Bricks, s in Shops} integer >= 0;

minimize cost:
  sum{s in Shops} order_shop[s] * fix_cost[s] +
  sum{b in Bricks, s in Shops} order_brick[b,s] * unit_price[b,s];

s.t. brick_at_least{b in Bricks}:
sum{s in Shops} order_brick[b,s] >= demand[b];

s.t. brick_not_too_much{b in Bricks}:
sum{s in Shops} order_brick[b,s] <= 10 * demand[b];

s.t. brick_shop_sync{b in Bricks, s in Shops}:
order_shop[s] >= order_brick[b,s] / max_bricks_from_shop;

s.t. shop_at_least{s in Shops}:
sum{b in Bricks} order_brick[b,s] * unit_price[b,s] >= min_order[s] * order_shop[s];

data;

param max_bricks_from_shop := 10000;

"""

AMPL_UNAVAILABLE_PRICE = 1000;

class OptimizerBase(object):
  
  def Load(self, parts, ldd_file_name, shop_data, allow_used=[]):
    self._ldd_file_name = ldd_file_name

    # dict str(part) -> int(quantity)
    self._parts_needed = self._GetPartsNeeded(parts, allow_used)
    assert set(self._parts_needed.keys()).issubset(shop_data.keys())

    # dict str(part) -> [dict(quantity, unit_price, shop_name)]
    self._shops_for_parts = self._FilterOffers(
        self._parts_needed, shop_data, allow_used)

    self._CalculateCandidateShops(self._shops_for_parts, self._parts_needed)
    self._shops_for_parts = self._RemoveExcludedshops(
        self._shops_for_parts, self._shops.keys())

    self._order_bricks = {}

  def PartsNeeded(self):
    return self._parts_needed

  def NumBricksNeeded(self):
    return sum(self._parts_needed[p] for p in self._parts_needed)

  def NumShopsAvailable(self, part):
    return len(self._shops_for_parts[part])

  def CriticalShops(self):
    return self._critical_shops

  def SupplementalShops(self):
    return self._supplemental_shops

  def UnselectedShops(self):
    return self._unselected_shops

  def Orders(self):
    if (len(self._order_bricks) == 0):
      return None
    return self._order_bricks

  def UnitPrice(self, shop, part):
    for s in self._shops_for_parts[part]:
      if s['shop_name'] == str(shop):
        return s['unit_price']
    return None
        
  def NetShopTotal(self, shop):
    return sum(
        self.UnitPrice(shop, part) * self._order_bricks[shop][part]
        for part in self._order_bricks[shop])
    
  def NetGrandTotal(self):
    return sum(
        self.NetShopTotal(shop)
        for shop in self._order_bricks)

  @staticmethod
  def _GetPartsNeeded(parts, allow_used):
    parts_needed = copy.copy(parts)
    for p in parts_needed:
      parts_needed[p] *= FLAGS.multiple
    return parts_needed

  @staticmethod
  def _FilterOffers(parts_needed, shops_for_parts, allow_used):
    filtered_shops_for_parts = {}
    for p in shops_for_parts:
      if p not in parts_needed:
        continue
      new_shops = []
      for s in shops_for_parts[p]:
        if (s['quantity'] >= parts_needed[p]
            and (s['condition'] == 'N'
                or p in allow_used or p.condition()=='A')
            and (not FLAGS.include_shops
                or s['shop_name'] in FLAGS.include_shops)
            and s['shop_name'] not in FLAGS.exclude_shops
            and (not FLAGS.include_countries
                or s['location'] in FLAGS.include_countries
                or s['shop_name'] in FLAGS.dont_exclude_shops)
            and (s['location'] not in FLAGS.exclude_countries
                or s['shop_name'] in FLAGS.dont_exclude_shops)):
          new_shops.append(s)
      filtered_shops_for_parts[p] = new_shops
    return filtered_shops_for_parts

  def _CalculateCandidateShops(self, shops_for_parts, parts_needed):
    if (len(parts_needed) == 0):
      print "There is nothing to optimize, got an empty list."
      sys.exit(0)
    # shops that we must take on the list to guarantee that we
    # have at least one shop for the part.
    critical_shops = {}

    # shops that we consider because they offer stuff cheaper.
    supplemental_shops = {}

    # [(str(part), int)]
    parts_by_rarity = sorted(
        ((p, len(shops_for_parts[p]))
        for p in shops_for_parts),
        key=lambda x: x[1])

    # First, establish at least one shop for each part and put it into
    # the criticical list.
    for p in parts_by_rarity:
      part = p[0]
      existing_shops = (
          set(s['shop_name'] for s in shops_for_parts[part])
          .intersection(critical_shops.keys()))
      found = False
      if not existing_shops:
        # We need one more critical shop, we use the cheapest for the part.
        for s in shops_for_parts[part]:
          if s['shop_name'] not in FLAGS.exclude_shops:
            critical_shops[s['shop_name']] = {
                'type': 'critical',
                'min_buy': s['min_buy'],
                'location': s['location']}
            found = True
            break
        assert found, ('Element %s was not found. This can mean: 1) The part '
                       'number or color of the element is different on '
                       'Bricklink and LDD and the mapping must be added to '
                       'lfxml.py 2) The part does not exist in this color.'
                       % str(p))

    # Second, populate the supplemental list with scores.
    base_score = 10 * (
        len(critical_shops) * FLAGS.shop_fix_cost / len(parts_by_rarity))
    for p in parts_by_rarity:
      part = p[0]
      existing_shops = (
          set(s['shop_name'] for s in shops_for_parts[part])
          .intersection(critical_shops.keys()))
      existing_price = min(
        s['unit_price']
        for s in shops_for_parts[part]
        if s['shop_name'] in existing_shops)
      for s in shops_for_parts[part]:
        if s['shop_name'] not in FLAGS.exclude_shops:
          if s['shop_name'] not in supplemental_shops:
            supplemental_shops[s['shop_name']] = {
                'type': 'supplemental',
                'min_buy': s['min_buy'],
                'location': s['location'],
                'score': 0.0}
          score = base_score / math.log(len(shops_for_parts[part]) + 1)
          score += (existing_price - s['unit_price']) * parts_needed[part]
          if (score > 0):
            supplemental_shops[s['shop_name']]['score'] -= score

    for s in critical_shops:
      if s in supplemental_shops:
        del supplemental_shops[s]

    self._critical_shops = copy.copy(critical_shops)

    if (FLAGS.consider_shops <= len(critical_shops)):
      print "You have to allow to consider at least %d shops for this query." % (
            len(critical_shops)+1)
      sys.exit(1)
    assert len(critical_shops) < FLAGS.consider_shops
    supplemental_list = sorted(
        (s for s in supplemental_shops),
        key=lambda x: supplemental_shops[x]['score'])
    supplemental_list = supplemental_list[
        :FLAGS.consider_shops - len(critical_shops)]
    result = critical_shops
    selected_supplemental_shops = dict(
        (s, supplemental_shops[s])
        for s in supplemental_list)
    result.update(selected_supplemental_shops)
    self._supplemental_shops = selected_supplemental_shops
    self._unselected_shops = dict(
        (s, supplemental_shops[s])
        for s in supplemental_shops
        if s not in supplemental_list and s not in critical_shops)
    self._shops = result

  @staticmethod
  def _RemoveExcludedshops(shops_for_parts, shops):
    result = {}
    for p in shops_for_parts:
      l = []
      for s in shops_for_parts[p]:
        if s['shop_name'] in shops:
          l.append(s)
      result[p] = l
    return result

""" Internal Optimizer class """

"""
Do part of the possible shop combinations, to be executed by one of
possibly many processes.
Note: This has to be a globally visible function instead of a member function
      of the BuiltinOptimizer class (which would look much better), because
      python's multiprocessing library cannot "pickle" class member functions,
      but it does need to picke the function that is executed by multiple
      processes.
"""
def MinimizePart(self, i_start, i_end):
  """ Small helper function to count the bits set in an integer """
  def BitCount(value):
    count = 0
    while (value):
      value &= value - 1
      count += 1
    return count

  shop_keys = sorted(self._shops.keys())
  shop_prices = {}
  for p in self._parts_needed:
    shop_prices[p] = { s['shop_name']: s['unit_price'] for s in self._shops_for_parts[p] }

  best_price = 1.e10
  best_list  = None
  best_order = None
  for i in xrange(i_start, i_end):
    # abort early if this combination contains 'too many shops'
    if (FLAGS.consider_shops > FLAGS.max_shops and
                 BitCount(i) > FLAGS.max_shops):
      continue
    # quick way to see if this combination has all parts available
    possible = True
    for p in self._parts_needed:
      if (not (self.shops_have_part[p] & i)):
        possible = False
        break
    if (possible):
      # generate list of shops from integer
      shops = [
        shop_keys[j]
        for j in xrange(len(self._shops))
        if i & 1 << j]
      price = 0.0
      for p in self._parts_needed:
        prices = [shop_prices[p][s] for s in set(shops)&set(shop_prices[p].keys())]
        if len(prices) > 0:
          min_price = min(prices)
          price += min_price * self._parts_needed[p]
        else:
          price = -1e-10
      price = price + len(shops) * FLAGS.shop_fix_cost

      if price >= 0 and price < best_price:
        best_price = price
        best_list  = shops
        best_order = {}
        for p in self._parts_needed:
          prices = {shop_prices[p][s]:s for s in set(shops)&set(shop_prices[p].keys())}
          min_price = min(prices)
          best_order.setdefault(prices[min_price],{})[p] = self._parts_needed[p]
  return (best_price, best_list, best_order)

class BuiltinOptimizer(OptimizerBase):
  def Run(self):
    sys.stdout.write('Optimizing...')
    sys.stdout.flush()
    # optimization: build dict that is used later for quick lookup whether
    # a certain combination of shops actually provides all necessary parts
    self.shops_have_part = {}
    shops = sorted(self._shops.keys())
    for p in self._parts_needed:
      self.shops_have_part[p] = 0
      for j in xrange(len(shops)):
        if (shops[j] in [ s['shop_name'] for s in self._shops_for_parts[p] ]):
          self.shops_have_part[p] += 1 << j
    # loop over all possible shop combinations, comparing price
    total = 2 ** FLAGS.consider_shops
    Nprocs = FLAGS.jobs
    pool = multiprocessing.Pool(processes=Nprocs)
    # devide work into more than Nprocs parts to increase load balance
    Nparts = Nprocs*10
    results = [pool.apply_async(
      MinimizePart, args=(self, total * k / Nparts, total * (k+1) / Nparts) )
      for k in xrange(Nparts)]
    # catch KeyboardInterrupt to be able to abort 'cleanly' with Ctrl+C
    best_price = 10**10
    best_list = None
    try:
      output = []
      for p in results:
        output.append(p.get(0xFFFFFFFF))
        for _best_price, _best_list, _best_order in output:
          if (_best_list and _best_price < best_price):
            best_price = _best_price
            best_list  = _best_list
            self._order_bricks = _best_order
        if (best_list):
          sys.stdout.write('\rOptimizing... %d%%, current best price: %.2f' % (
                           int(100*len(output)/len(results)), best_price))
        else:
          sys.stdout.write('\rOptimizing... %d%%' % (
                           int(100*len(output)/len(results))))
        sys.stdout.flush()
    except KeyboardInterrupt:
      return
    sys.stdout.write('\n')


class GlpkSolver(OptimizerBase):

  def Run(self):
    hash_str = str(self._parts_needed) + str(self._shops_for_parts)
    file_prefix = '%s/%s.%08x' % (
        FLAGS.cachedir,
        os.path.splitext(os.path.basename(self._ldd_file_name))[0],
        hash(hash_str) & 0xffffffff)
    ampl_file_name = '%s.ampl' % file_prefix
    solution_file_name = '%s.solution' % file_prefix
    
    if FLAGS.rerun_solver:
      print 'Forced rerun of solver for solution file %s' % solution_file_name
      self._RunSolver(ampl_file_name, solution_file_name)
    elif os.path.exists(solution_file_name):
      print 'Using cached solution file %s' % solution_file_name
    else:
      print 'Cached solution file %s not found, running solver' % (
          solution_file_name)
      try:
        os.makedirs(FLAGS.cachedir)
      except OSError:
        pass
      self._RunSolver(ampl_file_name, solution_file_name)
    try:
      solution_file = open(solution_file_name, 'r')
      self._Parse(solution_file)
    finally:
      solution_file.close()

  def _RunSolver(self, ampl_file_name, solution_file_name):
    try:
      ampl_file = open(ampl_file_name, 'w')
      self._Output(ampl_file)
      ampl_file.flush()
      args = ['glpsol', '--model', ampl_file.name,
              '--output', solution_file_name]
      if (FLAGS.glpk_limit_seconds):
        args.extend(['--tmlim', str(FLAGS.glpk_limit_seconds)])
      subprocess.call(args)
    finally:
      ampl_file.close()

  def _Parse(self, f):
    self._order_bricks = {}
    shop_re = re.compile(r'order_shop\[(.*)\]')
    brick_re = re.compile(r'order_brick\[(.*),(.*)\]')
    qty_re = re.compile(r'\A +\* +([0-9]+) +')
    for line in f:
      shop_match = shop_re.search(line)
      if shop_match:
        shop_name = GlpkSolver._TrimQuotes(shop_match.group(1))
        continue
      brick_match = brick_re.search(line)
      if brick_match:
        brick = item.item(brick_match.group(1))
        shop_name = GlpkSolver._TrimQuotes(brick_match.group(2))
        continue
      qty_match = qty_re.match(line)
      if qty_match:
        qty = int(qty_match.group(1))
        if qty:
          if brick:
            self._order_bricks.setdefault(shop_name, {})[brick] = int(qty)
        continue
      shop_name = None
      brick = None

  def _Output(self, f):
    f.write(AMPL_MODEL)
    f.write('set Bricks\n%s;\n\n' % '\n'.join(self._parts_needed.keys()))
    f.write('set Shops\n%s;\n\n' % '\n'.join(self._shops.keys()))
    f.write('param fix_cost :=\n%s;\n\n' % '\n'.join(
        '%s %.5f' % (s, FLAGS.shop_fix_cost) for s in self._shops))
    f.write('param min_order :=\n%s;\n\n' % '\n'.join(
        '%s %.5f' % (s, self._shops[s]['min_buy']) for s in self._shops))
    f.write('param demand :=\n%s;\n\n' % '\n'.join(
        '%s %d' % (p, self._parts_needed[p]) for p in self._parts_needed))
    f.write('param unit_price : %s :=\n' % ' '.join(p for p in self._shops))
    for p in self._shops_for_parts:
      f.write('%s' % p)
      for s in self._shops:
        if s in set(s['shop_name'] for s in self._shops_for_parts[p]):
          l = [o['unit_price'] for o in self._shops_for_parts[p] if o['shop_name'] == s]
          f.write(' %.5f' % l[0])
        else:
          f.write(' %.5f' % AMPL_UNAVAILABLE_PRICE)
      f.write('\n')
    f.write(';\n\n')
    f.write('end;\n')

  @staticmethod
  def _TrimQuotes(s):
    if s.startswith("'") and s.endswith("'"):
      return s[1:-1]
    else:
	  return s

def CreateOptimizer():
  if FLAGS.mode == 'builtin':
    return BuiltinOptimizer()
  elif FLAGS.mode == 'glpk':
    return GlpkSolver()
  else:
    raise NameError('Unknown mode %s' % FLAGS.mode)
