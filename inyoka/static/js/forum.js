/*
    static.js.forum
    ~~~~~~~~~~~~~~~

    JavaScript for the forum.

    :copyright: 2007 by Marian Sigler, Armin Ronacher.
    :license: GNU GPL.
*/


$(document).ready(function () {

  /* collapsable elements for the input forms */
  (function() {
    var toggle_state = {};
    $('.collapse').each(function () {
      $('.' + this.id + '_sub').hide();
      $(this)
        .addClass('collapsed_header')
        .click(toggle)
        .css('cursor', 'pointer');
      toggle_state[this.id] = true;
    }).click(function() {
      if (toggle_state[this.id]) {
        $(this).addClass('expanded_header').removeClass('collapsed_header');
        $('.' + this.id + '_sub').slideDown('normal');
        toggle_state[this.id] = false;
      } else {
        $(this).addClass('collapsed_header').removeClass('expanded_header');
        $('.' + this.id + '_sub').slideUp('normal');
        toggle_state[this.id] = true;
      }
    })})();
  
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

  // expand and collapse button for categories
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
      .prependTo('table.category_box tr.head a')
  })();
});
