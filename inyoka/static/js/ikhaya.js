/**
 * js.ikhaya
 * ~~~~~~~~~~
 *
 * Some javascript functions for the ikhaya application.
 *
 * :copyright: 2007 by Benjamin Wiegand.
 * :license: GNU GPL.
 */

$(function() {
  $('ul.comments > li.comment > p').each(function(i, comment) {
    $(comment).html($(comment).html().replace(/@(\d+)/g, '<a href="#comment_$1" class="comment_link">@$1</a>'));
  });
  $('.comment_link').mouseover(function() {
    var id = $(this).html().slice(1);
    var html = $('#comment_' + id + ' > p').html();
    this.tooltip = $('<div class="tooltip"></div>').html(html)
      .css({
        'left': this.offsetLeft,
        'top': this.offsetTop + 20,
        'position': 'absolute'})
      .appendTo($('body'));
  }).mouseout(function() {
    this.tooltip.remove()
  });
})
