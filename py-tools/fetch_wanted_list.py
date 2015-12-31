#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright (c) 2011-2012, Peter Dornbach
#               2014-2014, Frank Löffler
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
Fetches a wanted list from bricklink
"""

import json
import re
import sys
import urllib, urllib2, cookielib

import part_collector
import list_collector
import login_bl

import gflags
from HTMLParser import HTMLParser

FLAGS  = gflags.FLAGS

gflags.DEFINE_multistring(
    'wanted_list', 'default',
    'The name of the wanted list, to be fetched from Bricklink. Can be '
    'specified multiple times to concatenate lists.')
gflags.DEFINE_string(
    'user', None,
    'Your user name on Bricklink. This is necessary for operations that '
    'require you to log in. '
    'It will not be saved anywhere, so it has to be specified every time.')
gflags.DEFINE_string(
    'passwd', None,
    'Your password on Bricklink. This is necessary for operations that require '
    'you to log in. '
    'It will not be saved anywhere, so it has to be specified every time.')

LIST_LISTS_URL = ('http://www.bricklink.com/wantedView.asp')
# check which of these are really necessary
SHOP_LIST_URL = (
  'http://www.bricklink.com/wantedDetail.asp'
  '?catType=%(type)s'
  '&hideItems=Y'
  '&wantedSize=%(size)d'
  '&wantedStoreSort=2'
  '&wantedItemSort=0'
  '&wantedItemAsc=A'
  '&wantedMoreID=%(list_id)s'
  )
FLOAT_CHARS = set('0123456789.')
INT_CHARS = set('0123456789')

"""
Parses parts in a wanted list.
"""
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
    if (self._state == 1 and tag == "img" and
        attr_dict.setdefault('src', '').
          startswith('http://img.bricklink.com/P/')):
      m = re.match(r'([0-9]+)\/([^.]+)\.', attr_dict.setdefault('src', '')[27:])
      if m:
        self._current_part_dict['ITEMID'] = m.group(2)
        self._current_part_dict['COLOR']  = m.group(1)
        self._current_part_dict['TYPE']   = 'P'
        self._state = 2
    if (self._state == 1 and tag == "img" and
        attr_dict.setdefault('src', '').
          startswith('http://img.bricklink.com/I/')):
      m = re.match(r'([^.]+)\.', attr_dict.setdefault('src', '')[27:])
      if m:
        self._current_part_dict['ITEMID'] = m.group(1)
        self._current_part_dict['COLOR']  = 0
        self._current_part_dict['TYPE']   = 'I'
        self._state = 2
    # mark used/new/NA as to be read next in handle_data
    elif (self._state == 2 and tag == 'option' and 'selected' in attr_dict):
      self._state = 3
    elif (self._state == 4 and tag == 'input' and
          attr_dict.setdefault('type', '') == 'text' and
          attr_dict.setdefault('size', '') == '6'):
      minqnt = attr_dict.setdefault('value', '1')
      if (minqnt == ''):
        minqnt = '1'
      minqnt = int(minqnt)
      self._current_part_dict['MINQTY'] = minqnt
      self._collector.AddPart(
        part_id   = self._current_part_dict['ITEMID'],
        color_id  = self._current_part_dict['COLOR'],
        quantity  = self._current_part_dict['MINQTY'],
        condition = self._current_part_dict['CONDITION'],
        type      = self._current_part_dict['TYPE'])
      self._state = 1

  def handle_data(self, data):
    if self._state == 3:
      if data == 'N/A':
        self._current_part_dict['CONDITION'] = 'A'
      elif data == 'New':
        self._current_part_dict['CONDITION'] = 'N'
      elif data == 'Used':
        self._current_part_dict['CONDITION'] = 'U'
      else:
        print("Unknown condition %s found on BL." % data);
        sys.exit(1)
      self._state = 4

  def Result(self):
    return self._collector.Parts()

""" Parses list of wanted lists """
class ListHtmlParser(HTMLParser):
  def __init__(self, collector = list_collector.ListCollector()):
    HTMLParser.__init__(self)
    self._collector = collector
    self._state = 1
    self._current_list = ''

  def handle_starttag(self, tag, attrs):
    attr_dict = dict(attrs)
    if (self._state == 1 and tag == "select" and
        attr_dict.setdefault('name', '')=="wantedMoreID"):
      self._state = 2
    elif (self._state == 2 and tag == 'option' and
      attr_dict['value'] != '' and attr_dict['value'] != "0"):
      self._current_list = attr_dict['value']
      self._state = 3
    elif (self._state == 2 and tag == 'td'):
      self._state = 99
  
  def handle_data(self, data):
    if (self._state == 3):
      name = re.sub(' Wanted List$', '', re.sub('^My ', '', data))
      self._collector.AddList(self._current_list, name)
      self._state = 2

  def Result(self):
    return self._collector.Lists()

  def ResultbyName(self):
    return self._collector.ListsbyName()

""" Get some information about available wanted lists on Bricklink,
    in particular their Bricklink IDs.
"""
def FetchListInfo(opener):
  try:
    conn = opener.open(LIST_LISTS_URL)
  except:
    print "Could not connect to BrickLink. Check your connection and try again."
    sys.exit(1)
  parser = ListHtmlParser()
  html = conn.read()
  parser.feed(html)
  lists = parser.Result()
  listsbyName = parser.ResultbyName()
  return (lists, listsbyName)

""" Return a subset of given wanted lists that match a list of regular
    expressions
"""
def MatchWantedLists(lists, regexs):
  matched_lists = {}
  for list_id in lists:
    matched = False
    for regex in regexs:
      try:
        m = re.match('('+regex+')', lists[list_id]["name"])
      except:
        print "Wanted List \"%s\" is not a valid regular expression." % wlist
        sys.exit(1)
      if m:
        matched = True
    if (matched):
      matched_lists[list_id] = lists[list_id]["name"]
  return matched_lists

""" Fetch information about one type of things (parts/instructions/...) in a
    given wanted list and collect what is found in part_collector
"""
def FetchListPartsbyType(opener, list_id, ptype, parser):
  url_params = {
    'type'   : ptype,
    'list_id': list_id,
    'size'   : 500,
    }
  try:
    conn = opener.open(SHOP_LIST_URL % url_params)
  except:
    print 'Could not connect to BrickLink. Check your connection and try again.'
    sys.exit(1)
  html = conn.read()
  parser.feed(html)

""" Fetch the parts in wanted lists from Bricklink """
def FetchListParts():
  sys.stdout.write('Fetching lists...'+"\n")

  # First login
  opener = login_bl.BricklinkLogin()
  if (not opener):
    print 'Could not login to Bricklink.'
    sys.exit(1)
  # Get all wanted lists, in particular their IDs, to be used in queries
  (lists, listsbyName) = FetchListInfo(opener)

  # Match existing lists with command line argument (which allows for a regex)
  matched_lists = MatchWantedLists(lists, FLAGS.wanted_list)

  # print some information which lists will be considered
  print "Found %d lists on bricklink, of which %d matched:" % \
        (len(lists), len(matched_lists))
  for list in sorted(listsbyName.keys()):
    if (list in matched_lists.values()):
      print "* ", list
    else:
      print "  ", list

  # get information for all lists that matched
  collector = part_collector.PartCollector()
  for list_id in sorted(matched_lists, key=matched_lists.get):
    list_name = lists[list_id]["name"]
    sys.stdout.write(' processing '+list_name+' ('+list_id+')')
    parser = ResultHtmlParser()
    # regular parts first
    FetchListPartsbyType(opener, list_id, 'P', parser)
    # now instructions (have to be done separately apparently)
    FetchListPartsbyType(opener, list_id, 'I', parser)
    # In theory we should be able to do the following for boxes, but this
    # is untested, thus commented:
    #FetchListPartsbyType(opener, list_id, 'B', parser)

    # get results back from parser
    lists[list_id]["parts"] = parser.Result()
    sys.stdout.write(' ... %d parts in %d lots\n' %
                     (sum(lists[list_id]["parts"].values()),
                      len(lists[list_id]["parts"])))
    for part_id in lists[list_id]["parts"]:
      collector.AddPartbyKey(part_id, lists[list_id]["parts"][part_id])

  sys.stdout.flush()
  sys.stdout.write('\n')

  return collector.Parts()

