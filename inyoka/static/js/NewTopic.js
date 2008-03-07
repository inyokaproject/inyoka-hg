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
    var post_id = $(this).parent().parent()[0].id.substring(5);
    $('<a href="#" class="action action_quote">Zitat einfügen</a>')
      .click(function() {
        $.getJSON('/?__service__=forum.get_post', {post_id: post_id}, function(post) {
          if (post) {
            var editor = $('#id_text')[0].inyokaWikiEditor;
            editor.setSelection("'''" + post.author + "''' schrieb:\n" +
                                editor.quoteText(post.text));
          }
        });
        return false;
      })
      .appendTo($('<div class="linklist floatright" />').prependTo(this));
  });
});
