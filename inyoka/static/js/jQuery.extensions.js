/**
 * js/jQuery.extensions
 * ~~~~~~~~~~~~~~~~~~~~
 *
 * Various small jQuery extensions.
 *
 * :copyright: 2008 by Armin Ronacher,
 *             2010 by Christopher Grebs.
 * :license: GNU GPL.
 */


/**
 * Fetch all the nodes as long as a new node is found.
 */
jQuery.fn.nextWhile = function(expr) {
  var next = this.next(expr);
  var pos = 0;
  while (next.length > 0) {
    pos++;
    next = next.next(expr);
  }
  return this.nextAll(expr).slice(0, pos);
};
