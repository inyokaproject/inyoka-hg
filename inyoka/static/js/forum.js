/*
    static.js.forum
    ~~~~~~~~~~~~~~~

    JavaScript for the forum.

    :copyright: 2007 by Marian Sigler.
    :license: GNU GPL.
*/

toggle_state = {};

$(document).ready(function () {
//  $('body').prepend('<pre id="debug" style="width: 100%; border-width: 0; border-bottom-width: 1px; position: fixed; top: 0; left: 0;"></pre>');

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
  });
  
  $('#id_add_option').click(add_reply);
});

function add_reply() {
  count = $('.newtopic_polls_replies').length;
  $($('.newtopic_polls_replies')[count-1]).after('<dd class="newtopic_polls_sub newtopic_polls_replies">Antwort ' + (count + 1) + ': <input type="text" name="options" value="" />');
  $('#id_add_option').remove();
  $($('.newtopic_polls_replies')[count]).append(' <input type="submit" name="add_option" value="Weitere Antwort" id="id_add_option" />');
  $('#id_add_option').click(add_reply);
  return false;
}

