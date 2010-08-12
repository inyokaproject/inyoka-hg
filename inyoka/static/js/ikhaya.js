/**
 * js.ikhaya
 * ~~~~~~~~~~
 *
 * Some javascript functions for the ikhaya application.
 *
 * :copyright: 2007 - 2008 by Benjamin Wiegand.
 * :license: GNU GPL.
 */

function makeCommentLinks(elm) {
  $('p', elm).each(function(i, comment) {
    $(comment).html($(comment).html().replace(/@(\d+)/g, '<a href="#comment_$1" class="comment_link">@$1</a>'));
  });
  $('.comment_link').mouseover(function() {
    var id = $(this).html().slice(1);
    var userinfo = $('#comment_' + id + ' td.author p.username a').text() + ' schrieb:<br />'
    var html = $.map($('#comment_' + id + ' td.comment p'), function(e) {
      return $(e).html()
    }).join('<br />');
    this.tooltip = $('<div class="tooltip"></div>').html(userinfo + html)
      .css({
        'left': $(this).position().left,
        'top': $(this).position().top + 20,
        'position': 'absolute'})
      .appendTo($('body'));
  }).mouseout(function() {
    this.tooltip.remove()
  });
}

$(function() {
  if (navigator.appName.toLowerCase() == 'konqueror')
    return
  makeCommentLinks($('ul.comments > li.comment'));
})
