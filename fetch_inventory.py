#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright (c) 2014-2014, Frank Löffler
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
Fetches inventory of a store as wanted list. Useful if you do that on
your own store and use the wanted list to compare to other's prices.
"""

import json
import re
import sys
import urllib, urllib2, cookielib

import part_collector

import gflags
from HTMLParser import HTMLParser

FLAGS = gflags.FLAGS

gflags.DEFINE_string(
    'store_id', "default",
    'The id of the store. This is a numeric number associated to a shop. '
    'In particular, this is NOT the shop name. Eventually bltools will '
    'be able to get this ID automatically, but for now, go to the shop '
    'and look at the link for "Show all items". The value of the argument '
    '"h" is what you are looking for.')

# check which of these are really necessary
SHOP_LIST_URL = (
  'http://www.bricklink.com/storeDetail.asp'
  '?b=0' # no idea what this is, but it needs to be present
  '&h=%(store_id)s'
  )

# parse parts in a wanted list
class ResultHtmlParser(HTMLParser):
  def __init__(self, collector = None):
    if (collector == None):
      collector = part_collector.PartCollector()
    HTMLParser.__init__(self)
    self._collector = collector
    self._state = 1
    self._current_part_dict = {}
  
  def handle_starttag(self, tag, attrs):
    attr_dict = dict(attrs)
    if (self._state == 1 and tag == "tr" and
        attr_dict.setdefault('class', '') == 'tm'):
      self._state = 2
    if (self._state == 2 and tag == "a" and
        attr_dict.setdefault('href', '').startswith('/storeDetail.asp')):
      m = re.match(r'.*itemIDseq=(.+)', attr_dict.setdefault('href', ''))
      if m:
        self._current_part_dict['INTERNID'] = m.group(1)
        self._state = 3
    elif (self._state == 4 and tag == 'b'):
      self._state = 5
    elif (self._state == 7):
      self._current_part_dict['COLOR'] = 0
      self._current_part_dict['CONDITION'] = 'N'
      self._current_part_dict['TYPE'] = 'S'
      self._collector.AddPart(
        part_id   = self._current_part_dict['ITEMID'],
        color_id  = self._current_part_dict['COLOR'],
        quantity  = self._current_part_dict['MINQTY'],
        condition = self._current_part_dict['CONDITION'],
        type      = self._current_part_dict['TYPE'])
      self._state = 1

  def handle_data(self, data):
    if self._state == 3:
      self._current_part_dict['ITEMID'] = data
      self._state = 4
    if self._state == 5:
      self._current_part_dict['MINQTY'] = int(data)
      self._state = 6
    elif (self._state == 6):
      m = re.match(r'US \$(.+)', data)
      if m:
        self._current_part_dict['PRICE'] = m.group(1)
        self._state = 7

  def Result(self):
    return self._collector.Parts()


def FetchStoreInfo():
  sys.stdout.write('Fetching inventory...'+"\n")

  # get information for all lists that matched
  collector = part_collector.PartCollector()
  parser = ResultHtmlParser()
  # regular parts first
  url_params = {
    'store_id' : FLAGS.store_id,
    }
  try:
    conn = urllib.urlopen(SHOP_LIST_URL % url_params)
  except:
    print "Could not connect to BrickLink. Check your connection and try again."
    sys.exit(1)
  html = conn.read()
  parser.feed(html)
  # get results
  parts = parser.Result()
  sys.stdout.write(' ... %d parts in %d lots\n' %
                   (sum(parts.values()),len(parts)))
  for part_id in parts:
    collector.AddPartbyKey(part_id, parts[part_id])

  sys.stdout.flush()
  sys.stdout.write('\n')

  return collector.Parts()
