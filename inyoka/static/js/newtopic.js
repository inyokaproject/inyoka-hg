$(function() {
  function get_quote_cookie() {
    return $.cookie('multi_quote') ? $.cookie('multi_quote').split(',') : [];
  }

  function set_quote_cookie(ids) {
    if (ids.length == 0) {
      $.cookie('multi_quote', '', {expires: 'Thu, 01-Jan-70 00:00:01 GMT', path: '/'});
    } else {
      $.cookie('multi_quote', ids.join(','), {path: '/'});
    }
  }

  function make_quote_link(link, post_id) {
    link.text('Zitat')
      .removeClass('unquote')
      .unbind('click', remove_quote)
      .click(add_quote);
  }

  function make_unquote_link(link, post_id) {
    link.text('Zitat-Markierung entfernen')
      .addClass('unquote')
      .unbind('click', add_quote)
      .click(remove_quote)
  }

  function get_post_id(link) {
    return /quote(\d+)/.exec(link.attr('id'))[1];
  }

  function add_quote() {
    var link = $(this);
    var ids = get_quote_cookie();
    var post_id = get_post_id(link);
    ids.push(post_id);
    set_quote_cookie(ids);
    make_unquote_link(link, post_id);
    return false
  }

  function remove_quote() {
    var link = $(this);
    var ids = get_quote_cookie();
    var post_id = get_post_id(link);
    ids.pop($.inArray(post_id, ids));
    set_quote_cookie(ids);
    make_quote_link(link, post_id);
    return false;
  }

  $('.action_mark_quote').show().each(function(i, link) { 
    var link = $(link);
    var post_id = get_post_id(link);
    if ($.inArray(post_id, get_quote_cookie()) != -1) {
      make_unquote_link(link, post_id);
    } else {
      make_quote_link(link, post_id);
    }
  });
})
