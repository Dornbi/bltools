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
Fetches shop offers for items.
"""

import json
import re
import sys
import urllib

import gflags
from HTMLParser import HTMLParser

FLAGS = gflags.FLAGS

gflags.DEFINE_integer(
    'num_shops', 500,
    'Number of shops to fetch. Note that bricklink won\'t allow more than 500.')

SHOP_LIST_URL = (
  'http://www.bricklink.com/search.asp'
  '?pg=1'
  '&q=%(part)s'
  '&colorID=%(color)s'
  '&sz=%(num_shops)d'
  '&searchSort=P')
SHOP_NAME_REGEX = r'/store\.asp\?p=(.*)&itemID=.*'

FLOAT_CHARS = set('0123456789.')
INT_CHARS = set('0123456789')

class ResultHtmlParser(HTMLParser):
  def __init__(self, part_id):
    HTMLParser.__init__(self)
    self._state = 0
    self._result = []
    self._part_id = part_id
  
  def handle_starttag(self, tag, attrs):
    attr_dict = dict(attrs)
    if (self._state == 0 and tag == 'a' and
        attr_dict.setdefault('rel', '') == 'blcatimg'):
      self._state = 1
      self._current_dict = {}
    elif self._state == 2 and tag == 'b':
      self._state = 3
    elif self._state == 4 and tag == 'b':
      self._state = 5
    elif self._state == 6 and tag == 'a':
      m = re.match(SHOP_NAME_REGEX, dict(attrs)['href'])
      if m:
        self._current_dict['shop_name'] = m.group(1)
        self._result.append(self._current_dict)
      self._state = 0

  def handle_data(self, data):
    if self._state == 1 and data.startswith('Used'):
      self._current_dict['condition'] = 'U'
    elif self._state == 1 and data.startswith('New'):
      self._current_dict['condition'] = 'N'
    elif self._state == 1 and data.startswith('Loc:'):
      m = re.match(r'Loc: (.*), Min Buy: (.*)', data)
      if m:
        self._current_dict['location'] = m.group(1)
        min_buy_str = (
            ''.join(ch for ch in m.group(2) if ch in FLOAT_CHARS))
        if len(min_buy_str) > 0:
          self._current_dict['min_buy'] = float(min_buy_str)
        else:
          self._current_dict['min_buy'] = 0.0
    elif self._state == 1 and data.startswith('Qty:'):
      self._state = 2
    elif self._state == 3:
      self._current_dict['quantity'] = int(
          ''.join(ch for ch in data if ch in INT_CHARS))
      self._state = 4
    elif self._state == 5:
      self._current_dict['unit_price'] = float(
          ''.join(ch for ch in data.split(' ')[1] if ch in FLOAT_CHARS))
      self._state = 6

  def Result(self):
    # Unify duplicate lots
    shops = {}
    for shop in self._result:
      shop_name = shop['shop_name']
      if (shop_name not in shops) or (
          shops[shop_name]['quantity'] < shop['quantity']):
        shops[shop_name] = shop
    return sorted(
        [shops[shop] for shop in shops],
        key=lambda x: x['unit_price'])


def FetchShopInfo(part_dict, filename):
  outfile = open(filename, 'w')

  shop_items = {}
  sys.stdout.write('Fetching offers...')
  sys.stdout.flush()
  for part in part_dict:
    url_params = {
      'part': part.split('-')[0],
      'color': part.split('-')[1],
      'num_shops': FLAGS.num_shops}
    conn = urllib.urlopen(SHOP_LIST_URL % url_params)
    parser = ResultHtmlParser(str(part))
    parser.feed(conn.read())
    shop_items[part] = parser.Result()
    sys.stdout.write('\rFetching items... %d of %d'
                     % (len(shop_items), len(part_dict)))
    sys.stdout.flush()
    
  outfile.write(json.dumps(shop_items))
  outfile.close()
  sys.stdout.write('\n')
