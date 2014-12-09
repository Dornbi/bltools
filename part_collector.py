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
Collects BrickLink parts.
"""

import item

class PartCollector:
  def __init__(self):
    self._parts = {}

  def AddPart(self, part_id, color_id=0, quantity = 1, condition = 'A', type = 'P'):
    # parts (bricks ect.) - usually something with a color
    if (type == 'P'):
      key = item.item('%s__%s__%s__%s' % (type, part_id, condition, color_id))
    # everything else (instructions, boxes, sets) - something without color
    else:
      key = item.item('%s__%s__%s' % (type, part_id, condition))
    self._parts[key] = self._parts.get(key, 0) + quantity

  def InitParts(self, parts):
    self._parts = parts

  def AddPartbyKey(self, key, quantity = 1):
    self._parts[key] = self._parts.get(key, 0) + quantity

  # Remove parts in the argument from this set of parts. This is intended to remove
  # items in your inventory from your wanted_lists (for an order), but for that to
  # work, your inventory items cannot have the 'any/A' condition, because we wouldn't
  # know what to subtract in that case, unless your wanted list also only contains 'A'
  # items.
  def Subtract(self, to_subtract):
    result = self._parts
    for part in sorted(to_subtract, reverse=True):
      # If we find the exact part, subtract it
      if (part in result):
        quantity = min(result[part], to_subtract[part])
        to_subtract[part] -= quantity
        result     [part] -= quantity
        if (result[part] == 0):
          del(result[part])
      # If we find 'any condition' for this part in the wanted list, subtract that too
      partA = part.set_condition('A')
      if (partA in result):
        quantity = min(result[partA], to_subtract[part])
        to_subtract[part] -= quantity
        result    [partA] -= quantity
        if (result[partA] == 0):
          del(result[partA])
    return result

  def Parts(self):
    return self._parts

