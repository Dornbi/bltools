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
#     * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
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
import datetime
import json
import os
import os.path
import re
import sys
import subprocess

import lfxml
import gflags

FLAGS = gflags.FLAGS

gflags.DEFINE_string(
    'mode', 'builtin',
    '"builtin" runs the built in optimizer that works up to about '
    '--consider_shops=20. "gplk" will invoke the external glpsol '
    'linear program solver.')

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
    'The maximum number of shops to evaluate. Affects mode=builtin only.')

gflags.DEFINE_integer(
    'consider_shops', 20,
    'Number of shops to consider. For mode=builtin the max feasible value is '
    '20. With mode=glpk it can be much more, about 60 or 100 may be still ok '
    'depending on the model.')


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
  
  def Load(self, parts, ldd_file_name, shops_file_name, allow_used=[]):
    self._ldd_file_name = ldd_file_name
    # part: '%s-%s' % part_no, color

    # dict str(part) -> int(quantity)
    self._parts_needed = self._GetPartsNeeded(parts, allow_used)
    unfiltered_shops_for_parts = self._LoadshopData(shops_file_name)
    assert set(self._parts_needed.keys()).issubset(
        unfiltered_shops_for_parts.keys())

    # dict str(part) -> [dict(quantity, unit_price, shop_name)]
    self._shops_for_parts = self._FilterOffers(
        self._parts_needed, unfiltered_shops_for_parts)

    self._CalculateCandidateShops(self._shops_for_parts, self._parts_needed)
    self._shops_for_parts = self._RemoveExcludedshops(
        self._shops_for_parts, self._shops.keys())

    self._order_shops = {}
    
  def Orders(self):
    return self._order_bricks

  @staticmethod
  def _GetPartsNeeded(parts, allow_used):
    parts_needed = copy.copy(parts)
    for p in parts_needed:
      parts_needed[p] *= FLAGS.multiple
    return parts_needed

  @staticmethod
  def _LoadshopData(shops_for_parts_file_name):
    shop_file = open(shops_for_parts_file_name, 'r')
    try:
      shops_for_parts = json.loads(shop_file.read())
    finally:
      shop_file.close()
    return shops_for_parts

  @staticmethod
  def _FilterOffers(parts_needed, shops_for_parts):
    filtered_shops_for_parts = {}
    for p in shops_for_parts:
      if p not in parts_needed:
        continue
      new_shops = []
      for s in shops_for_parts[p]:
        if (s['quantity'] >= parts_needed[p]
            and (s['condition'] == 'N'
                or ((p in FLAGS.include_used or 'all' in FLAGS.include_used)
                    and p not in FLAGS.exclude_used))
            and (not FLAGS.include_shops
                or s['shop_name'] in FLAGS.include_shops)
            and s['shop_name'] not in FLAGS.exclude_shops
            and (not FLAGS.include_countries
                or s['location'] in FLAGS.include_countries)
            and s['location'] not in FLAGS.exclude_countries):
          new_shops.append(s)
      filtered_shops_for_parts[p] = new_shops
    return filtered_shops_for_parts

  def _CalculateCandidateShops(self, shops_for_parts, parts_needed):
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
        assert found

    # Second, populate the supplemental list with scores.
    base_score = 3 * (
        len(existing_shops) * FLAGS.shop_fix_cost / len(parts_by_rarity))
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
          score = base_score / len(shops_for_parts[part])
          score += (existing_price - s['unit_price']) * parts_needed[part]
          if (score > 0):
            supplemental_shops[s['shop_name']]['score'] -= score

    for s in critical_shops:
      if s in supplemental_shops:
        del supplemental_shops[s]

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
    self._critical_shops = critical_shops
    self._supplemental_shops = selected_supplemental_shops
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


class BuiltinOptimizer(OptimizerBase):
  def Run(self):
    best_price = 10**10
    best_list = None
    sys.stdout.write('Optimizing...')
    sys.stdout.flush()
    total = 2 ** FLAGS.consider_shops
    for k in xrange(100):
      for i in xrange(total * k / 100, total * (k+1) / 100):
        shops = [
            self._shops.keys()[j]
            for j in xrange(len(self._shops))
            if i & 1 << j]
        if len(shops) <= FLAGS.max_shops:
          p = self._TotalPrice(shops)
          if p and p < best_price:
            best_price = p
            best_list = shops
      sys.stdout.write('\rOptimizing... %d%%' % (k + 1))
      sys.stdout.flush()
    sys.stdout.write('\n')
    if best_list:
      self._UpdateOrders(best_list)

  def _TotalPrice(self, shop_list):
    price = 0.0
    for p in self._parts_needed:
      shop_prices = [
          s['unit_price']
          for s in self._shops_for_parts[p]
          if s['shop_name'] in shop_list]
      if shop_prices:
        price += min(shop_prices) * self._parts_needed[p]
      else:
        return None
    return price + len(shop_list) * FLAGS.shop_fix_cost

  def _UpdateOrders(self, shop_list):
    self._order_bricks = {}
    for p in self._parts_needed:
      for s in self._shops_for_parts[p]:
        if s['shop_name'] in shop_list:
          self._order_bricks.setdefault(s['shop_name'], {})[p] = (
              self._parts_needed[p])
          break;

  def _PrintOrders(self, shop_list):
    orders_per_shop = {}
    total_per_shop = {}
    for p in self._parts_needed:
      for s in self._shops_for_parts[p]:
        if s['shop_name'] in shop_list:
          orders_per_shop.setdefault(s['shop_name'], [])
          orders_per_shop[s['shop_name']].append({
            'part': p,
            'unit_price': s['unit_price'],
            'quantity': self._parts_needed[p],
            'total_price': s['unit_price'] * self._parts_needed[p]
            })
          total_per_shop.setdefault(s['shop_name'], 0.0)
          total_per_shop[s['shop_name']] += s['unit_price'] * self._parts_needed[p]
          break;
    for shop in orders_per_shop:
      print 'Shop %s, total %.2f' % (shop, total_per_shop[shop])
      for part in orders_per_shop[shop]:
        print (' part %(part)s, unit_price %(unit_price).2f,'
               ' qty %(quantity)d, total_price %(total_price).2f' % part)
      print


class GlpkSolver(OptimizerBase):

  def Run(self):
    file_prefix = '%s/%s.%x' % (
        FLAGS.cachedir,
        os.path.splitext(os.path.basename(self._ldd_file_name))[0],
        hash(str(self._parts_needed) + str(self._shops_for_parts)) & 0xffffffff)
    ampl_file_name = '%s.ampl' % file_prefix
    ampl_file = open(ampl_file_name, 'w')
    solution_file_name = '%s.solution' % file_prefix
    if not os.path.exists(solution_file_name):
      try:
        self._Output(ampl_file)
        ampl_file.flush()
        subprocess.call([
            'glpsol', '--model', ampl_file.name,
            '--output', solution_file_name, '--tmlim', '30'])
      finally:
        ampl_file.close()

    try:
      solution_file = open(solution_file_name, 'r')
      self._Parse(solution_file)
    finally:
      solution_file.close()

  def _Parse(self, f):
    self._order_bricks = {}
    shop_re = re.compile(r'order_shop\[(.*)\]')
    brick_re = re.compile(r'order_brick\[\'(.*)\',(.*)\]')
    qty_re = re.compile(r'\A +\* +([0-9]+) +')
    for line in f:
      shop_match = shop_re.search(line)
      if shop_match:
        shop_name = shop_match.group(1)
        continue
      brick_match = brick_re.search(line)
      if brick_match:
        brick = brick_match.group(1)
        shop_name = brick_match.group(2)
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


def CreateOptimizer():
  if FLAGS.mode == 'builtin':
    return BuiltinOptimizer()
  elif FLAGS.mode == 'glpk':
    return GlpkSolver()
  else:
    raise NameError('Unknown mode %s' % FLAGS.mode)
