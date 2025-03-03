/**
 * js.overall
 * ~~~~~~~~~~
 *
 * Some general scripts for the whole portal (requires jQuery).
 *
 * :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
 * :license: GNU GPL, see LICENSE for more details.
 */

$(document).ready(function () {
  var loginForm = null;

  // preload images
  (function () {
    var container = $('<div>').appendTo('body').css({
      height: 0,
      overflow: 'hidden'
    });
    $.each(['img/tabbar_border_hover.png'], function () {
      $('<img />').attr('src', $STATIC_URL + this).appendTo(container);
    });
  })();

  // add a hide message link to all flash messages
  $.each($('div.message'), function (i, elm) {
    $(elm).prepend($('<a href="#" class="hide" />').click(function () {
      if ($(this).parent().hasClass('global')) {
        $.post('/?__service__=portal.hide_global_message', {});
      }
      $(this).parent().slideUp('slow');
      return false;
    }));
  });

  // hide search words on click
  $('a.hide_searchwords').click(function () {
    $(this).parent().slideUp('slow');
    $('span.highlight').removeClass('highlight');
    return false;
  });

  // Make TOC links expandable.
  (function () {
    //Execute this function only when if there are tocs.
    if (!$('.toc').length) return;
    if (navigator.userAgent.match(/konqueror/i)) return;

    // create a link to hide a toc
    $('.toc .head').append(
    $('<a> [-]</a>').toggle(function () {
      $(this).text(' [+]').parent().next().slideUp('fast');
    }, function () {
      $(this).text(' [-]').parent().next().slideDown('fast');
    }));

    $('.toc').each(function () {
      toc = $(this);
      // find out depth of old toc, so we can make ours look the same in the beginning
      var _classes = this.className.split(/\s+/);
      for (var i = 0; i < _classes.length; i++) {
        if (_classes[i].match(/^toc-depth-(\d+)$/)) {
          tocDepth = parseInt(_classes[i].slice(10), 10);
          break;
        }
      }
      if (typeof tocDepth === 'undefined') return;

      // mark old toc for later deletion
      toc.find('ol').addClass('originaltoc');

      // create first level
      newtoc = $('<ol class="arabic"></ol>').hide().insertAfter(toc.find('.head'));

      // Create the whole tocTree
      var
      tocTree = "",
           // becomes Elementtree
          level = 1,
           // which toc-level am I?
          headerLinks = $('.headerlink'); // Give me all the headers
      for (var i = 0; i < headerLinks.length; i++) {
        var link = $(headerLinks[i]).parent().attr("id");
        var linkText = $(headerLinks[i]).parent().text();
        var linkText = linkText.substring(0, linkText.length - 1).htmlEscape();
        var thisClass = $(headerLinks[i]).parent().parent().attr("class");

        if (i < headerLinks.length - 1) {
          // we are not the last headline
          nextClass = $(headerLinks[i + 1]).parent().parent().attr("class");
        } else {
          // after the last headline a first-level HL would follow
          nextClass = "section_1";
        }

        nextLevel = parseInt(nextClass.match(/^section_(\d+)$/)[1], 10);
        if (nextLevel > level) {
          // append "<li><ol>" !! without closing tags !!
          tocTree += '<li><a href="#' + link + '" class="crosslink">' + linkText + '</a>';
          tocTree += '<ol class="arabic toc-item-depth-' + level + '">';
          level++;
        } else {
          //  There is no deeper level
          tocTree += '<li><a href="#' + link + '">' + linkText + '</a></li>';
          while (nextLevel < level) {
            tocTree += '</ol></li>';
            level--;
          }
        }
      }
      newtoc.append(tocTree);

      toc.find('.originaltoc').remove();
      newtoc.show();
      //we have to hide all sublevels, create [+/-], and the click-event
      toc.find(":not(.originaltoc) ol").each(function () {
        folder = $('<a class="toctoggle"> [-] </a>');
        folder.insertBefore($(this));
        folder.toggle(

        function () {
          $(this).text(' [+] ').next().slideUp('fast');
        }, function () {
          $(this).text(' [-] ').next().slideDown('fast');
        });

        var _classes = this.className.split(/\s+/);
        for (var i = 0; i < _classes.length; i++) {
          if (_classes[i].match(/^toc-item-depth-(\d+)$/)) {
            curDepth = parseInt(_classes[i].slice(15), 10);
            break;
          }
        }
        if (curDepth >= tocDepth) {
          folder.click();
        }
      });

    });
  }());

  // if we have JavaScript we style the search bar so that it looks
  // like a firefox search thingy and apply some behavior
  (function () {
    if (navigator.appName.toLowerCase() == 'konqueror') return;
    var
    initialized = false,
        $currentSearchArea = $('select.search_area').val(),
        $currentAreaName = $('select.search_area option:selected').html(),
        areaPopup = $('<ul class="search_area" />'),
        searchArea = $('select.search_area').hide();
    $('.search_query').addClass('area_' + $currentSearchArea);
    $('form.search').submit(function () {
      var url = $(this).attr('action'),
          tmp = $('input.search_query').val();
      if ($('input.search_query').hasClass('default_value')) tmp = '';
      if (tmp) {
        url += '?query=' + encodeURIComponent(tmp) + '&area=' + $currentSearchArea;
      }
      document.location.href = url;
      return false;
    }).append($('<div class="search_expander" />').click(function () {
      if (!initialized) {
        initialized = true;
        $('option', searchArea).each(function () {
          var currentArea = $(this).val();
          var item = $('<li />').text($(this).text()).addClass('area_' + $(this).val()).click(function () {
            $currentAreaName = $(this).html();
            $('.search_query').removeClass('area_' + $currentSearchArea);
            $currentSearchArea = currentArea;
            $currentAreaName = $('select.search_area option[value=' + $currentSearchArea + ']').html();
            $('.search_query').addClass('area_' + $currentSearchArea);
            $('li', areaPopup).each(function () {
              $(this).removeClass('active');
            });
            $(this).addClass('active').parent();
            $('.search_query').focus();
            areaPopup.hide();
            return false;
          }).appendTo(areaPopup);
          if (currentArea == $currentSearchArea) item.addClass('active');
        });
        areaPopup.prependTo('form.search');
      } else areaPopup.toggle();
      return false;
    }));
    $('.search_query').addClass('search_query_js').blur(function () {
      var e = $(this);
      if (e.val() == '' || e.val() == $currentAreaName) e.addClass('default_value').val($currentAreaName);
    }).focus(function () {
      var e = $(this);
      if (e.hasClass('default_value')) e.val('').removeClass('default_value');
    });
    $('.search_query').blur();
    $(document).click(function () {
      if (areaPopup.is(':visible')) areaPopup.hide();
      if (loginForm && loginForm.is(':visible')) loginForm.slideUp();
    });
  })();

  // add a sidebar toggler if there is an sidebar
  (function () {
    var sidebar = $('.navi_sidebar');
    if (!sidebar.length) return;
    var togglebutton =
    $('<button class="navi_toggle_up" title="Navigation ausblenden" />').click(function () {
      $('.content').toggleClass('content_sidebar');
      sidebar.toggle();
      togglebutton.toggleClass('navi_toggle_up').toggleClass('navi_toggle_down');
      if ($IS_LOGGED_IN) $.get('/?__service__=portal.toggle_sidebar', {
        hide: !sidebar.is(':visible'),
        component: window.location.hostname.split('.')[0]
      });
      return false;
    }).insertAfter('form.search');
    if ($SIDEBAR_HIDDEN) togglebutton.click();
  })();

  // use javascript to deactivate the submit button on click
  // we don't make the elements really disabled because then
  // the button won't appear in the form data transmitted
  (function () {
    var submitted = false;
    $('form').submit(function () {
      if ($(this).hasClass('nosubmitprotect')) return true;
      if (submitted) return false;
      $('input[type="submit"]').addClass('disabled');
      submitted = true;
    });
  })();

  // add links to the "package" macro
  $('.package-list').each(function (i, elm) {
    var tmp = $('.bash', elm),
        apt = tmp[0],
        aptitude = tmp[1];
    $(aptitude).hide();
    $($('p', elm)[0]).append(
    $('<a>apt-get</a>').click(function () {
      $(this).parent().children().css('font-weight', '');
      $(this).css('font-weight', 'bold');
      $(apt).show();
      $(aptitude).hide();
    }).click(), ' ', $('<a>aptitude</a>').click(function () {
      $(this).parent().children().css('font-weight', '');
      $(this).css('font-weight', 'bold');
      $(aptitude).show();
      $(apt).hide();
    }), ' ', $('<a>apturl</a>').attr('href', 'apt://' + $.trim($(apt).text()).split(' ').slice(3).join(',')));
  });

  // the javascript powered login form
  (function () {
    $('#login_link').click(function () {
      if (loginForm == null) {
        loginForm = $('#js_login_form').prependTo('body').submit(function (event) {
          loginForm.slideDown();
          return true;
        }).click(function (event) {
          event.stopPropagation();
        });
      }
      loginForm.fadeIn();
      $('#js_login_username').focus();
      return false;
    });
  })();


  $('div.code').add('pre').each(function () {
    if (this.clientHeight < this.scrollHeight) {
      $(this).after('<div class="codeblock_resizer" title="vergrößern">vergrößern</div>')
             .css('height', '15em').css('max-height', 'none')
             .data('original_height', this.clientHeight);
    }
  });

  (function () {
    if (navigator.appName.toLowerCase() == 'konqueror') return;
    $('.codeblock_resizer').click(function () {
      $codeblock = $(this).prev();
      if (!$codeblock.hasClass('codeblock_expanded')) {
        $codeblock.addClass('codeblock_expanded');
        $codeblock.animate({
          'height': $codeblock[0].scrollHeight
        }, 500);
        this.innerHTML = this.title = 'verkleinern';
      } else {
        $codeblock.removeClass('codeblock_expanded');
        $codeblock.animate({
          'height': $codeblock.data('original_height')
        }, 500);
        this.innerHTML = this.title = 'vergrößern';
      }
    });
  })();

  // Add a version switcher to the `PPA` template.
  (function () {
    var SHORT_NOTATION_VERSIONS = ['karmic', 'lucid', 'maverick'];

    var set_version = function (dom) {
      var link = $(dom);
      group = link.parent().parent();
      version = link.text().toLowerCase();
      group.find('.ppa-code').remove();
      sel = group.find('.selector');

      link.addClass('active').siblings('a').removeClass('active');

      sel.after('<pre class="ppa-code">' + group.data('long_notation_text').replace(/VERSION/, version) + '</div></pre>');
      if ($.inArray(version, SHORT_NOTATION_VERSIONS) > -1) {
        sel.after('<p class="ppa-code">Für die <strong>sources.list</strong>:</p>');
        sel.after('<p class="ppa-code">' + group.data('short_notation_text') + '</p>');
      }
      return false;
    };

    $('.ppa-list-outer').each(function () {
      $this = $(this);
      var versions = [],
          version;
      classes = this.className.split(/\s+/);
      for (var i = 0; i < classes.length; i++) {
        if (classes[i].match(/^ppa-version-/)) {
          version = classes[i].slice(12);
          versions.push(version);
        }
      }

      $this.data('short_notation_text', $this.find('.ppa-list-short-code .contents p').html());
      $this.data('long_notation_text', $this.find('.ppa-list-long-code .contents pre').html());

      $this.children('.contents').remove();
      sel = $('<p class="selector">').appendTo($this);
      sel.prepend('<strong>Version: </strong>');
      var set_version_callback = function () {
        return set_version(this);
      };
      for (var i = 0; i < versions.length; i++) {
        version = versions[i];
        latest_link = $('<a href="#">').text(version.substr(0, 1).toUpperCase() + version.substr(1))
                                       .click(set_version_callback).appendTo(sel).after('<span class="linklist"> | </span>');
      }
      latest_link.next('.linklist').remove(); // remove last |
      set_version(latest_link[0]);
    });
  })();

  // Add a version switcher to the `Fremdquelle` template.
  (function () {
    var set_version = function (link) {
      version = $(link).text().toLowerCase();
      $(link).addClass('active').siblings('a').removeClass('active');
      sel = $(link).parent();
      sel.siblings('pre').text(sel.data('deb-url-orig').replace(/VERSION/, version));
      return false;
    };

    $('.thirdpartyrepo-outer').each(function () {
      var versions = [],
          set_version_callback = function () {
          return set_version(this);
          },
          last_link;
      classes = this.className.split(/\s+/);
      for (var i = 0; i < classes.length; i++) {
        if (classes[i].match(/^thirdpartyrepo-version-/)) {
          version = classes[i].slice(23);
          versions.push(version);
        }
      }
      sel = $('<div class="selector">').insertBefore($(this).find('.contents pre'));
      sel.prepend('<strong>Version: </strong>').data('deb-url-orig', $(this).find('.contents pre').text());
      for (var i = 0; i < versions.length; i++) {
        last_link = $('<a href="#">').text(versions[i].substr(0, 1).toUpperCase() + versions[i].substr(1))
                                      .click(set_version_callback).appendTo(sel).after('<span class="linklist"> | </span>');
      }
      last_link.next().remove(); // remove last |
      set_version(last_link[0]);
      return true;
    });
  })();
});

(function() {
  /* OpenID Integration */
  OpenIDHelper = Class.$extend({
    __init__: function(target, openid_providers) {
      var self = this;
      var target = $(target);
      for (var provider in openid_providers) {
        var alt = provider.capitalize() + " benutzen";
        var element = $('<img src="' + $STATIC_URL + 'img/openid/' + provider + '.png" class="' + provider + '" alt="' + alt + '" title="' + alt + '" />')
          .click(function() {
            $(target).val('');
            p = $(this).attr('class')
            if (openid_providers[p]['url'] == null) {
              $(target).val('http://');
              $(target).focus();
            } else {
              self.setSelection($(target), openid_providers[p]['url'], '{username}', true);
            }
          })
          .css('cursor', 'pointer');

        element.insertAfter($(target));
      }
    },

    setSelection: function(area, text, match, reselect) {
      var t = $(area)[0];
      if (typeof t.selectionStart != 'undefined') {
        var
          start = text.indexOf(match),
          end = text.indexOf(match) + match.length;
        var
          s1 = t.value.substring(0, start),
          s2 = t.value.substring(end);

        t.value = s1 + text + s2;
        t.focus();
        if (reselect) {
          t.selectionStart = start;
          t.selectionEnd = end;
        }
        else
          t.selectionEnd = t.selectionStart = start + text.length;
      }
      else if (typeof document.selection != 'undefined') {
        t.focus();
        var range = document.selection.createRange();
        range.text = text;
      }
    }
  });
})();

String.prototype.htmlEscape = function () {
  return this.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/, "&quot;");
};

String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
};
