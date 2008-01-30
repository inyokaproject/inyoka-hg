/**
 * js.overall
 * ~~~~~~~~~~
 *
 * Some general scripts for the whole portal (requires jQuery).
 *
 * :copyright: 2007 by Christoph Hack, Armin Ronacher.
 * :license: GNU GPL.
 */


$(document).ready(function() {
  // add a hide message link to all flash messages
  $.each($('div.message'), function(i, elm) {
    $(elm).append($('<a href="#" class="hide" />')
      .click(function() {
        $(this).parent().slideUp('slow');
        return false;
      })
    )
  });

  // hide search words on click
  $('a.hide_searchwords')
    .click(function() {
      $(this).parent().parent().slideUp('slow');
      $('span.highlight').removeClass('highlight');
      return false;
    });

  // add a link to the user map if javascript available and on the index page
  (function() {
    var navigation = $('h3.navi_ubuntuusers').next();
    if (navigation.is('ul'))
      $('<li><a href="/map/">Benutzerkarte</a></li>')
        .appendTo(navigation);
  })();

  // if we have JavaScript we style the search bar so that it looks
  // like a firefox search thingy and apply some behavior
  (function() {
    var
      initialized = false,
      $currentSearchArea = $('select.search_area').val(),
      $currentAreaName = $('select.search_area option[@selected]').html(),
      areaPopup = $('<ul class="search_area" />'),
      searchArea = $('select.search_area').hide();
      $('.search_query').addClass('area_' + $currentSearchArea);
    $('form.search')
      .submit(function() {
        var url = $(this).attr('action'), tmp;
        if (tmp = $('input.search_query').val()) {
          if ($('input.search_query').hasClass('default_value'))
            tmp = '';
          url += '?query=' + encodeURIComponent(tmp);
          if ($currentSearchArea != 'all')
            url += '&area=' + $currentSearchArea;
        }
        document.location.href = url;
        return false;
      })
      .append($('<div class="search_expander" />')
        .click(function() {
          if (!initialized) {
            initialized = true;
            $('option', searchArea).each(function() {
              var currentArea = $(this).val();
              var item = $('<li />')
                .text($(this).text())
                .addClass('area_' + $(this).val())
                .click(function() {
                  $currentAreaName = $(this).html();
                  $('.search_query').removeClass('area_' + $currentSearchArea);
                  $currentSearchArea = currentArea;
                  $currentAreaName = $('select.search_area option[@value=' +
                                       $currentSearchArea + ']').html()
                  $('.search_query').addClass('area_' + $currentSearchArea);
                  $('li', areaPopup).each(function() {
                    $(this).removeClass('active');
                  });
                  $(this).addClass('active').parent();
                  $('.search_query').focus();
                  areaPopup.hide();
                  return false;
                }).appendTo(areaPopup);
              if (currentArea == $currentSearchArea)
                item.addClass('active');
            });
            areaPopup.prependTo('form.search');
          }
          else areaPopup.toggle();
          return false;
        }));
      $('.search_query').addClass('search_query_js')
        .blur(function() {
          var e = $(this);
          if (e.val() == '') {
            e.addClass('default_value').val($currentAreaName);
          }
        })
        .focus(function() {
          var e = $(this);
          if (e.hasClass('default_value')) {
            e.val('').removeClass('default_value');
          }
        });
      $('.search_query').val('').blur();
    $(document).click(function() {
      if (areaPopup.is(':visible'))
        areaPopup.hide();
    });
  })();

  // add a sidebar toggler if there is an sidebar
  (function() {
    var sidebar = $('.navi_sidebar');
    var togglebutton = $('<button class="navi_toggle_up" title="Navigation ' +
                         'ausblenden" ></button>');
    if (sidebar.length) togglebutton
      .click(function() {
        var content = $('.content_sidebar');
        sidebar.toggle()
        content.toggleClass('content_full')
        togglebutton.toggleClass('navi_toggle_up')
        togglebutton.toggleClass('navi_toggle_down')
        return false;
      }).insertAfter('form.search');
  })();
});
