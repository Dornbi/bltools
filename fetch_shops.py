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
import os
import urllib
import datetime
import fetch_bricks_and_pieces as BaP

import gflags
from HTMLParser import HTMLParser

FLAGS = gflags.FLAGS

gflags.DEFINE_integer(
    'num_shops', 500,
    'Number of shops to fetch. Note that bricklink won\'t allow more than 500.')

gflags.DEFINE_boolean(
    'bap', False,
    'Also include the Lego Bricks and Pieces shop in the query.')

SHOP_LIST_URL_QUERY = (
  'http://www.bricklink.com/search.asp'
  '?pg=1'
  '&q=%(part)s'
  '&sz=%(num_shops)d'
  '&searchSort=P')
SHOP_LIST_URL_ITEMID = (
  'http://www.bricklink.com/search.asp'
  '?pg=1'
  '&itemID=%(part)s'
  '&sz=%(num_shops)d'
  '&searchSort=P')
SHOP_NAME_REGEX = r'/store\.asp\?p=(.*)&itemID=.*'

CATALOG_URL = (
  'http://www.bricklink.com/catalogItem.asp?%(type)s=%(part)s' )
CATALOG_ITEM_ID_REGEX       = r'<A HREF="search\.asp\?itemID=([^&"]*)'
CATALOG_ITEM_ID_COLOR_REGEX = r'<A HREF="search\.asp\?itemID=([^&"]*)&colorID=%s'

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
    elif self._state == 1 and tag == 'img':
      self._current_dict['lotpic'] = attr_dict.setdefault('src', '')
      self._state = 2
    elif self._state == 3 and tag == 'b':
      self._state = 4
    elif self._state == 5 and tag == 'b':
      self._state = 6
    elif self._state == 7 and tag == 'a':
      m = re.match(SHOP_NAME_REGEX, dict(attrs)['href'])
      if m:
        self._current_dict['shop_name'] = m.group(1)
        self._result.append(self._current_dict)
      self._state = 0

  def handle_data(self, data):
    if self._state == 2 and data.startswith('Used'):
      self._current_dict['condition'] = 'U'
    elif self._state == 2 and data.startswith('New'):
      self._current_dict['condition'] = 'N'
    elif self._state == 2 and data.startswith('Loc:'):
      m = re.match(r'Loc: (.*), Min Buy: (.*)', data)
      if m:
        self._current_dict['location'] = m.group(1)
        min_buy_str = (
            ''.join(ch for ch in m.group(2) if ch in FLOAT_CHARS))
        if len(min_buy_str) > 0:
          self._current_dict['min_buy'] = float(min_buy_str)
        else:
          self._current_dict['min_buy'] = 0.0
    elif self._state == 2 and data.startswith('Qty:'):
      self._state = 3
    elif self._state == 4:
      self._current_dict['quantity'] = int(
          ''.join(ch for ch in data if ch in INT_CHARS))
      self._state = 5
    elif self._state == 6:
      self._current_dict['unit_price'] = float(
          ''.join(ch for ch in data.split(' ')[1] if ch in FLOAT_CHARS))
      self._state = 7

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


def FetchShopInfo(part_dict):

  shop_items = {}
  sys.stdout.write('Fetching offers...')
  sys.stdout.flush()
  for part in part_dict:
    partfile_name = '%s/%s.shopdata' % (FLAGS.cachedir, part)
    try:
      partfile_lastmod = datetime.datetime.fromtimestamp(os.path.getmtime(partfile_name))
    except:
      # If file cannot be accessed for any reason...
      partfile_lastmod = -1
    sys.stdout.write('\rFetching items... %d of %d'
                     % (len(shop_items)+1, len(part_dict)))
    if (partfile_lastmod == -1 or
        (datetime.datetime.now() - partfile_lastmod).total_seconds() > FLAGS.shopcache_timeout):
      sys.stdout.write('             ')
      # get itemID first. We have to do this because the search otherwise brings
      # up all kinds of items for instructions or boxes (the actual sets)
      URL = CATALOG_URL % {'type': part.type(), 'part': part.id() }
      conn = urllib.urlopen(URL)
      html = conn.read()
      if part.type() == 'P':
        m = re.search(CATALOG_ITEM_ID_COLOR_REGEX % part.color(), html)
      else:
        m = re.search(CATALOG_ITEM_ID_REGEX, html)
      part_id = None
      if (m):
        part_id = m.group(1)
        url_params = {
          'part': part_id,
          'num_shops': FLAGS.num_shops}
        URL = SHOP_LIST_URL_ITEMID % url_params
      else:
        if (part.type() != 'P'):
          print "\nBricklink ItemID not found for %s, maybe not available?" % part
          sys.exit(1)
        url_params = {
          'part': part.id(),
          'num_shops': FLAGS.num_shops}
        URL = SHOP_LIST_URL_QUERY % url_params
      if (part.condition() != 'A'):
        URL += "&invNew=%s" % part.condition()
      if (part.type() == 'P'):
        URL = "%s&colorID=%s" % (URL, part.color())
      conn = urllib.urlopen(URL)
      parser = ResultHtmlParser(str(part))
      html = conn.read()
      parser.feed(html)
      shop_items[part] = parser.Result()
      partfile = open(partfile_name, "w")
      partfile.write(json.dumps(parser.Result()))
      partfile.close()
    else:
      sys.stdout.write(" (from cache)")
      partfile = open(partfile_name, "r")
      try:
        data = json.loads(partfile.read())
      finally:
        partfile.close()
      shop_items[part] = data
    if (FLAGS.bap and part.type() == 'P'):
      BaPInfo = BaP.BaPFetchShopInfo(part.id(), int(part.color()))
      if (BaPInfo != None):
        shop_items[part].append(BaPInfo)
    sys.stdout.flush()
    
  sys.stdout.write('\n')
  return shop_items
