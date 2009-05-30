/*
    static.js.forum
    ~~~~~~~~~~~~~~~

    JavaScript for the forum.

    :copyright: 2007-2008 by Marian Sigler, Armin Ronacher, Christopher Grebs.
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


  function doSubscription(type, slug, tags) {
    // Get the matching string for replacement. Since the two buttons (top and bottom)
    // are in the same macro we just need to check for one buttons text at all.
    var action = $(tags[0]).text()=='abbestellen' ? 'unsubscribe' : 'subscribe';
    var url = "/?__service__=forum." + action;

    $.post(url, {
      type: type,
      slug: slug
    }, function(data) {
      // Bind new events and change button's text.
      $(tags).fadeOut('fast');
      $(tags).text(action=='subscribe' ? 'abbestellen' : 'abonnieren');
      $(tags).fadeIn('fast');
    });

    return false;
  };

  (function() {
    $('a.action_subscribe.subscribe_topic').each(function() {
      $(this).click(function() {
        doSubscription('topic', $(this).attr('id'), $('a.action_subscribe.subscribe_topic'));
        return false;
    })});

    $('a.action_subscribe.subscribe_forum').each(function() {
      $(this).click(function() {
        doSubscription('forum', $(this).attr('id'), $('a.action_subscribe.subscribe_forum'));
        return false;
    })});
  })();


  /* Display some more informations about the ubuntu version */
  (function() {
    $('select[@name="ubuntu_version"]').change(function() {
      var text_unstable = 'Dies ist die momentane <a href="{LL}">Entwicklungsversion</a> von Ubuntu';
      var text_lts = 'Dies ist eine <a href="{LL}">LTS (Long Term Support)</a> Version';
      var text_current = 'Dies ist die momentan <a href="{LL}>aktuelle Version</a> von Ubuntu';
      var url = "/?__service__=forum.get_version_details";
      var version_str = $(this).find('option:selected').val();

      var with_link = function(text, data) { return text.replace(/\{LL\}/, data.link); };

      $.getJSON(url, {
        version: version_str
      }, function(data) {
        if (data.class == 'unstable') {
          $('span#version_info').attr('class', 'unstable')
            .html(with_link(text_unstable, data));
        } else if (data.lts) {
          $('span#version_info').attr('class', 'lts')
            .html(with_link(text_lts, data));
        } else if (data.current) {
          $('span#version_info').attr('class', 'current')
            .html(with_link(text_current, data));
        } else {
          $('span#version_info').attr('class', '').text('');
        }
      });

      return false;
    })
  })();
});



