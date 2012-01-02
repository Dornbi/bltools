bltool is a tool that converts Lego Digital Designer files into Bricklink
orders. During the process, it fetches relevant offers from Bricklink and
computes the more or less optimal set of shops to order from to minimize
the cost.

Prerequisites:

* The Python runtime. It can be downloaded for Windows, Max and Linux from
  http://www.python.org/download/
  It needs Python version 2.6 or later (will not work with Python 3)

* For proper optimization, it needs the 'glpsol' command from the
  GNU Linear Programming Kit
  http://www.gnu.org/software/glpk/
  
Installation:

Download and unpack the bltools.zip file in a directory.

Check external dependencies:
* the 'python' command must be in your path
* the 'glpsol' command must be in your path

Usage:

Run 'bltool.py' from the command line.

FAQ:

Q: Will there be a GUI version?
A: Not from me. It is easy to use the command line version.

Q: Will there be support for other inputs than Lego Digital Desinger?
A: Maybe, if there is enough interest. Also, the tool is open sorce, feel
   free to contribute.
   
Q: The glpsol optimizer runs for hours.
A: I am not an optimizer expert. Maybe there is something that can be done
   about it, but I have no ideas.

Author:
Peter Dornbach, 2011.
Official location:
http://code.google.com/p/bltools

Version history:

0.1: Initial version.
