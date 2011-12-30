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
Returns a wanted list XML file.
"""

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
