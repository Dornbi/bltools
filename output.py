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
Outputs the result of the optimizer.
"""

import textwrap

MAX_CHARS=80

CSS = """
body {
  font-family: sans-serif;
}
.shophead {
  font-weight: bold;
}
.rightalign {
  text-align: right;
}
"""

HTML_SKELETON = """
<html>
<head>
<title>%s</title>
<style type="text/css">%s</style>
</head>
<body>
<h3>%s</h3>
<h4>Total cost</h4>
<table>
%s
</table>
<h4>Orders</h4>
<table>
%s
</table>
<h4>Shops considered</h4>
<table>
%s
</table>
<h4>
</body>
</html>
"""

TOTAL_SKELETON = """
<tr>
<td>Net cost (without shipping):</td>
<td class="rightalign">%.2f</td>
</tr>
<tr>
<td>Gross cost (shipping fee %.2f / shop):</td>
<td class="rightalign">%.2f</td>
</tr>
"""

ORDER_SHOP = """
<tr class="shophead">
<td colspan="4">%s</td>
</tr>
<tr>
<td colspan="3">Net cost (without shipping):</td>
<td class="rightalign">%.2f</td>
</tr>
<tr>
<td colspan="3">Gross cost (with shipping):</td>
<td class="rightalign">%.2f</td>
</tr>
<tr><td>&nbsp;</td></tr>
<tr class="shophead">
<td>Part (id-color)</td>
<td class="rightalign">Quantity</td>
<td class="rightalign">Unit price</td>
<td class="rightalign">Total price</td>
</tr>
"""

ORDER_ROW = """
<tr>
<td>%s</td>
<td class="rightalign">%d</td>
<td class="rightalign">%.2f</td>
<td class="rightalign">%.2f</td>
</tr>
"""

ORDER_SEPARATOR="""
<tr><td>&nbsp;</td></tr>
"""

SHOP_LINK = 'http://www.bricklink.com/store.asp?p=%s'
CATALOG_LINK = 'http://www.bricklink.com/catalogItem.asp?P=%s&colorID=%s'
PART_LINK = 'http://www.bricklink.com/search.asp?Q=%s&colorID=%s'

def LeftPad(v, width):
  s = str(v)
  return ' ' * (width - len(s)) + s

def RightPad(v, width):
  s = str(v)
  return s + ' ' * (width - len(s))

def MakeLink(url, text):
  return '<a href="%s">%s</a>' % (url, text)

def PrintListText(list):
  s = ', '.join(str(e) for e in sorted(list))
  for l in textwrap.wrap(s, MAX_CHARS - 1):
    print ' %s' % (l)

def PrintShopsText(optimizer):
  print 'Critical shops:'
  PrintListText(optimizer.CriticalShops().keys())
  print 'Supplemental shops:'
  PrintListText(optimizer.SupplementalShops().keys())

def PrintOrdersText(optimizer, shop_fix_cost):
  print 'Orders:'
  orders = optimizer.Orders()
  for shop in sorted(orders):
    shop_total = optimizer.NetShopTotal(shop)
    print ' %s: (Total %s, Gross %s)' % (
        RightPad(shop, 20),
        LeftPad('%.2f' % shop_total, 8),
        LeftPad('%.2f' % (shop_total + shop_fix_cost), 8))
    for part in orders[shop]:
      unit_price = optimizer.UnitPrice(shop, part)
      num_bricks = orders[shop][part]
      print '  %s: %s (Unit price %s, Total %s)' % (
          RightPad(part, 10),
          LeftPad(num_bricks, 4),
          LeftPad('%.2f' % unit_price, 8),
          LeftPad('%.2f' % (unit_price * num_bricks), 8))

def PrintAllHtml(
    optimizer,
    shop_fix_cost,
    ldd_file_name,
    output_html_file_name):
  f = open(output_html_file_name, "w")
  try:
    title = 'Orders for %s' % ldd_file_name
    orders = optimizer.Orders()
    total_cost = optimizer.NetGrandTotal()
    total_fragment = TOTAL_SKELETON % (
        total_cost,
        shop_fix_cost,
        total_cost + shop_fix_cost * len(orders))
    orders_fragment = ''
    for shop in orders:
      shop_cost = optimizer.NetShopTotal(shop)
      orders_fragment += ORDER_SHOP % (
          MakeLink(SHOP_LINK % shop, shop),
          shop_cost,
          shop_cost + shop_fix_cost)
      for part in orders[shop]:
        num_parts = orders[shop][part]
        unit_price = optimizer.UnitPrice(shop, part)
        orders_fragment += ORDER_ROW % (
            MakeLink(PART_LINK % tuple(part.split('-')), part),
            num_parts,
            unit_price,
            unit_price * num_parts)
      orders_fragment += ORDER_SEPARATOR

    considered_fragment = ''
    html = HTML_SKELETON % (
        title, CSS, title,
        total_fragment, orders_fragment, considered_fragment)
    f.write(html)
  finally:
    f.close()
