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

  // expand and collapse button for categories
  $('table.collapsible tr.head a').before('<a href="#" class="collapse"></a>');
  $('table.collapsible tr.head a.collapse')
    .click(function() {
        var tr = $(this).parent().parent().get(0);
        collapse(tr);
        return false;
    });
  var re_slug = /\/category\/([^/]+)\//;

  // revert the last stored collapse status from the cookie
  $('table.collapsible tr.head a').each(function() {
    var status = $.cookie('forum_collapse');
    status = status ? status.split('/') : [];
    m = re_slug.exec($(this).attr('href'));
    if (m) {
      var collapsed = false;
      for (i = 0; i < status.length; i++) {
        if (status[i] == m[1]) {
          var tr = $(this).parent().parent().get(0);
          collapse(tr);
          continue;
        }
      }        
    }
    });
});


function add_reply() {
  count = $('.newtopic_polls_replies').length;
  $($('.newtopic_polls_replies')[count-1]).after('<dd class="newtopic_polls_sub newtopic_polls_replies">Antwort ' + (count + 1) + ': <input type="text" name="options" value="" />');
  $('#id_add_option').remove();
  $($('.newtopic_polls_replies')[count]).append(' <input type="submit" name="add_option" value="Weitere Antwort" id="id_add_option" />');
  $('#id_add_option').click(add_reply);
  return false;
}

// collapse a forum category and save the status as cookie
function collapse(tr) {
  var cid = $(tr).attr('id');
  var collapsed = $(tr).find('a').hasClass('expand');
  if (collapsed) {
    $(tr).find('a.expand').removeClass('expand').addClass('collapse');
    $('tr.'+cid).show();
  }
  else {
    $(tr).find('a.collapse').removeClass('collapse').addClass('expand');
    $('tr.'+cid).hide();
  }
  return;

  // XXX: old collapse code follows here:
  var inside = false;
  var link = $(tr).find('a.collapse');
  var status = $.cookie('forum_collapse');
  status = status ? status.split('/') : new Array();
  var re_slug = /\/category\/([^/]+)\//;
  var m = re_slug.exec($($(tr).find('a').get(1)).attr('href'));
  for (i = 0; i < status.length; i++) {
    if (status[i] == m[1]) {
      status.splice(i, 1);
      break;
    }
  }
  if (link.length > 0) {
    link.removeClass('collapse').addClass('expand');
    status.push(m[1]);
  } else 
    $(tr).find('a.expand').removeClass('expand').addClass('collapse');
  $.cookie('forum_collapse', status.join('/'));
  $('table.collapsible tr').each(function() {
  if ($(this).hasClass('head'))
    inside = tr == $(this).get(0);
  if (inside && ($(this).hasClass('entry') || $(this).hasClass('empty')))
    $(this).toggle();
  });
}
