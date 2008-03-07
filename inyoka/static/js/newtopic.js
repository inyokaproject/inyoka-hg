/**
 * js.newtopic
 * ~~~~~~~~~~~
 *
 * Adds support for inserting quotes into the WikiEditor.
 *
 * :copyright: 2008 by Armin Ronacher.
 * :license: GNU GPL.
 */

$(function() {
  $('table.topic div.postinfo').each(function() {
    $('<a href="#" class="action action_quote">Foo</a>')
      .click(function() {
        alert(this);
      })
      .appendTo($('<div class="linklist floatright" />').prependTo(this));
  });
});
