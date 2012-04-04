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
Parses and generates a wanted list XML file.
"""

import xml.sax
import xml.sax.handler

import part_collector


class WantedListPartCollector(xml.sax.handler.ContentHandler):
  def __init__(self, collector = part_collector.PartCollector()):
    self._collector = collector
    self._current_part_dict = {}
    self._current_elem_name = ''
    self._current_content = ''

  def startElement(self, name, attrs):
    upperName = name.upper()
    if upperName == 'ITEM':
      self._current_part_dict = {}
    else:
      self._current_elem_name = upperName
    self._current_content = ''

  def endElement(self, name):
    upperName = name.upper()
    if upperName == 'ITEM':
      # We've finished the item, so collect it.
      part_id = self._current_part_dict['ITEMID']
      color_id = self._current_part_dict['COLOR']
      quantity = int(self._current_part_dict['MINQTY'] or 1)
      self._collector.AddPart(part_id, color_id, quantity)
    elif self._current_elem_name != '':
      # This is the end of a (probably nested) element, so add its content
      # to the part dict.
      self._current_part_dict[self._current_elem_name] = \
          self._current_content.strip()

  # This is called multiple times per element, so we append the content each
  # time.
  def characters(self, content):
    self._current_content += content


def CollectBricklinkParts(filename, collector):
  wanted_list_part_collector = WantedListPartCollector(collector)
  try:
    f = open(filename, 'r')
    xml.sax.parse(f, wanted_list_part_collector)
  finally:
    f.close()

def WantedList(parts_dict, allow_used=[], extra_tags=None):
  result = ''
  result += '<INVENTORY>\n'
  for key in sorted(parts_dict):
    result += '<ITEM>'
    result += '<ITEMTYPE>P</ITEMTYPE>'
    result += '<ITEMID>%s</ITEMID>' % key.split('-')[0]
    result += '<COLOR>%s</COLOR>' % key.split('-')[1]
    result += '<MINQTY>%s</MINQTY>\n' % parts_dict[key]
    result += '<NOTIFY>N</NOTIFY>'
    if key not in allow_used:
      result += '<CONDITION>N</CONDITION>'
    if extra_tags:
      result += extra_tags
    result += '</ITEM>\n'
  result += '</INVENTORY>\n'
  return result
