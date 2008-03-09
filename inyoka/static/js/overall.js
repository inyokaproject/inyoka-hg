/**
 * js.overall
 * ~~~~~~~~~~
 *
 * Some general scripts for the whole portal (requires jQuery).
 *
 * :copyright: 2007 by Christoph Hack, Armin Ronacher, Benjamin Wiegand.
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
      $(this).parent().slideUp('slow');
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
          if (e.val() == '')
            e.addClass('default_value').val($currentAreaName);
        })
        .focus(function() {
          var e = $(this);
          if (e.hasClass('default_value'))
            e.val('').removeClass('default_value');
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

  // use javascript to deactivate the submit button on click
  // we don't make the elements really disabled because then
  // the button won't appear in the form data transmitted
  (function() {
    var submitted = false;
    $('form').submit(function() {
      if (submitted)
        return false;
      $('input[@type="submit"]').addClass('disabled');
      submitted = true;
    });
  })();

  // add links to the "package" macro
  $('.package-list').each(function(i, elm) {
    var [apt, aptitude] = $('.bash', elm);
    $(aptitude).hide();
    $($('p', elm)[0]).append(
      $('<a>apt-get</a>').click(function() {
        $(this).parent().children().css('font-weight', '');
        $(this).css('font-weight', 'bold');
        $(apt).show();
        $(aptitude).hide();
      }).click(), ' ',
      $('<a>aptitude</a>').click(function() {
        $(this).parent().children().css('font-weight', '');
        $(this).css('font-weight', 'bold');
        $(aptitude).show();
        $(apt).hide();
      }), ' ',
      $('<a>apturl</a>').attr('href', 'apt://' + $(apt).text().split(' ')
                                                       .slice(3).join(' '))
    )
  });

  $('#user_error_report_button').click(function() {
    $('body')
      .append('
        <div id="user_error_report">
          <p>Hier kannst du Fehler in der Software melden. Bitte verwende diese Formular nur für Fehler die offensichtlich welche sind, nicht für Fragen o.ä., dafür gibts das Forum.</p>
          <form method="post" action="http://ubuntuusers.local:8080">
            <p><label for="id_title">Ganz kurz, worum gehts:</label> <input id="id_title" size="50" name="title"/> </p>
            <p><label for="id_text">Details:</label> <textarea style="width: 100%;" rows="3" cols="100" name="title"/></textarea></p>
            <p><input type="submit" value="Fehlermeldung speichern" /></p>
          </form>
        </div>');
//      .style('margin-bottom', '#XXX: ??');
  });
});


$('#user_error_report_button').click(function() {
  $('body').append('<div id="user_error_report" style="border-top: 2px solid rgb(170, 170, 170); margin: 0pt; padding: 0pt; position: fixed; bottom: 0pt; width: 100%; background-color: rgb(238, 238, 238); clear: both;"><p>Hier kannst du Fehler in der Software melden. Bitte verwende diese Formular nur für Fehler die offensichtlich welche sind, nicht für Fragen o.ä., dafür gibts das Forum.</p>
<form method="post" action="http://ubuntuusers.local:8080">
<p><label for="id_title">Ganz kurz, worum gehts:</label> <input id="id_title" size="50" name="title"/> </p>
<p><label for="id_text">Details:</label> <textarea style="width: 100%;" rows="3" cols="100" name="title"/></textarea></p>
<p><input type="submit" value="Fehlermeldung speichern" /></p>
</form>
</div>')
});

