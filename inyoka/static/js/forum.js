/*
    static.js.forum
    ~~~~~~~~~~~~~~~

    JavaScript for the forum.

    :copyright: 2007 by Marian Sigler, Armin Ronacher.
    :license: GNU GPL.
*/


$(function () {
  /* collapsable elements for the input forms */
  $('dt.collapse').each(function() {
    $(this).nextWhile('dd').hide().addClass('collapse_enabled');
    $(this).click(function() {
      var children = $(this).nextWhile('dd'), lastChanged = 0;
      $(this).toggleClass('collapsed');
      (function next() {
        $(children[lastChanged]).slideToggle(30, function() {
          if (++lastChanged < children.length)
            next();
        });
      })();
    }).addClass('collapse_enabled collapsed');
  });
  
  /* poll helpers */
  (function() {
    $('#id_add_option').click(function addReply() {
      count = $('.newtopic_polls_replies').length;
      $($('.newtopic_polls_replies')[count-1])
        .after('<dd class="newtopic_polls_sub newtopic_polls_replies">Antwort ' +
        (count + 1) + ': <input type="text" name="options" value="" />');
      $('#id_add_option').remove();
      $($('.newtopic_polls_replies')[count])
        .append(' <input type="submit" name="add_option" value="Weitere Antwort" ' +
                'id="id_add_option" />');
      $('#id_add_option').click(addReply);
      return false;
    })})();

  /* expand and collapse button for categories */
  (function() {
    var toggleState = {};
    $('<a href="#" class="collapse" />')
      .click(function() {
        var head = $(this).parent().parent().parent();
        head.nextUntil('tr.head').toggle();
        $(this).toggleClass('collapsed');
        $('table.category_box tr.head').each(function() {
          toggleState[this.id.substr(9)] = $('a.collapsed', this).length > 0;
        });
        var hidden = []
        for (id in toggleState)
          if (toggleState[id])
            hidden.push(id);
        $.get('/?__service__=forum.toggle_categories', {hidden: hidden});
        return false;
      })
      .prependTo('table.category_box tr.head a');
  
    /* this function is used by the index template */
    hideForumCategories = function(hidden_categories) {
      $('table.category_box tr.head').each(function() {
        if ($.inArray(this.id.substr(9), hidden_categories) >= 0) {
          $(this).nextUntil('tr.head').hide();
          $('a.collapse', this).addClass('collapsed');
        }
      });
    };
  })();
});
