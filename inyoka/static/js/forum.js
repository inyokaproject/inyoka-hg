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
      $(this).toggleClass('collapsed').nextWhile('dd').toggle();
    }).addClass('collapse_enabled collapsed');
  });
  
  /* poll helpers */
  (function() {
    $('#id_add_option').click(function addReply() {
      count = $('.newtopic_polls_replies').length;
      $($('.newtopic_polls_replies')[count-1])
        .after('<dd class="newtopic_polls_replies collapse_enabled">Antwort ' +
        (count + 1) + ': <input type="text" name="options" value="" /></dd>');
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

  $('div.code').add('pre').each(function () {
    if (this.clientHeight < this.scrollHeight) {
      $(this)
        .after('<div class="codeblock_resizer" title="vergrößern">vergrößern</div>')
        .css('height', '15em').css('max-height', 'none')
        .data('original_height', this.clientHeight);
    }
  });
  (function() {
    if (navigator.appName.toLowerCase() == 'konqueror')
      return
    $('.codeblock_resizer').click(function () {
      $codeblock = $(this).prev();
      if (!$codeblock.hasClass('codeblock_expanded')) {
        $codeblock.addClass('codeblock_expanded');
        $codeblock.animate({'height': $codeblock[0].scrollHeight}, 500);
        this.innerHTML = this.title = 'verkleinern';
      } else {
        $codeblock.removeClass('codeblock_expanded');
        $codeblock.animate({'height': $codeblock.data('original_height')}, 500);
        this.innerHTML = this.title = 'vergrößern';
      }
    });
  })();


  function doSubscription(kind, type, slug, tag) {
    if (kind == "subscribe") {
      var url = "/?__service__=forum.subscribe";
    } else if (kind == "unsubscribe") {
      var url = "/?__service__=forum.unsubscribe";
    }

    var new_kind = kind=='subscribe' ? 'unsubscribe' : 'subscribe';

    $.post(url, {
      type: type,
      slug: slug
    }, function(data) {
      //TODO: so something...
    });

    // Bind new events and change button's text.
    $(tag).text(kind=='subscribe' ? 'abbestellen' : 'abonnieren');
    $(tag).removeClass(kind+'_'+type).addClass(new_kind+'_'+type);
    $(tag).unbind('click.subscribe');
    $(tag).bind('click.subscribe', function() { doSubscription(new_kind, type, slug, tag) });

    return false;
  };

  (function() {
    $('a.action_subscribe.unsubscribe_topic').bind('click.subscribe', function() {
      doSubscription('unsubscribe', 'topic', $(this).attr('id'), $(this));
      return false;
    });

    $('a.action_subscribe.subscribe_topic').bind('click.subscribe', function() {
      doSubscription('subscribe', 'topic', $(this).attr('id'), $(this));
      return false;
    });

    $('a.action_subscribe.unsubscribe_forum').bind('click.subscribe', function() {
      doSubscription('unsubscribe', 'forum', $(this).attr('id'), $(this));
      return false;
    });

    $('a.action_subscribe.subscribe_forum').bind('click.subscribe', function() {
      doSubscription('subscribe', 'forum', $(this).attr('id'), $(this));
      return false;
    });
  })();



});



