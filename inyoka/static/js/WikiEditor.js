/**
 * js.WikiEditor
 * ~~~~~~~~~~~~~
 *
 * Implements a small addon to normal textareas so that they give a better
 * text control for wiki markup.  This module provides one public object
 * `WikiEditor`.  Usage as follows::
 *
 *    new WikiEditor('#my_editor');
 *
 * The toolbar is added dynamically to the editor so that users without
 * JavaScript don't get a useless UI.
 *
 * :copyright: 2007 by Armin Ronacher.
 * :license: GNU GPL.
 */


/* create a closure for all of our stuff so that we don't export the
   helper functions and variables.  The only thing that is defined as
   a global is the `WikiEditor`. */
(function() {

  /* indentation size */
  var INDENTATION = 2;

  /* number of colors */
  var COLORS = [
    '#DA0000',
    '#D97000',
    '#D9BF00',
    '#A6D900',
    '#45D900',
    '#00D99B',
    '#00ADD9',
    '#0057D9',
    '#0000D9',
    '#8200D9',
    '#910074',
    '#474747',
    '#888888',
    '#C5C5C5'
  ];

  /**
   * Helper function that creates a button object.
   */
  var button = function(id, title, callback, profiles) {
    return function(editor) {
      if (!profiles || $.inArray(editor.profile, profiles) > -1)
        return $('<a href="#" class="button" />')
          .attr('id', 'button-' + id)
          .attr('title', title)
          .append($('<span />').text(title))
          .click(function(evt) {
            evt.preventDefault();
            return callback.call(editor, evt);
          });
    }
  };

  /**
   * helper function that creates a dropdown object.
   */
  var dropdown = function(id, title, items, callback, profiles) {
    return function(editor) {
      if (profiles && $.inArray(editor.profile, profiles))
        return;
      var dropdown = $('<select />')
        .attr('id', 'dropdown-' + id)
        .attr('title', title)
        .append($('<option class="title" value="" />').text(title))
        .change(function(evt) {
          callback.call(editor, evt);
        });
      $.each(items, function() {
        dropdown.append(this);
      });
      dropdown[0].selectedIndex = 0;
      return dropdown;
    }
  }

  /**
   * one item in a dropdown
   */
  var item = function(value, title) {
    return $('<option />').val(value).text(title || value);
  }

  /**
   * factory function for combined usage with "button".
   */
  var insert = function(format, def) {
    return function(evt) {
      return this.insertTag(format, (typeof def == 'undefined')
                            ? 'Formatierter Text' : def);
    };
  }

  /**
   * Helper function that formats a `Date` object into a iso8601
   * format string.
   */
  var formatISO8601 = function(date) {
    var t;
    return (
      date.getUTCFullYear() + '-' +
      (t = date.getUTCMonth(), t < 9 ? '0' : '') + (t + 1) + '-' +
      (t = date.getUTCDate(), t < 10 ? '0' : '') + t + 'T' +
      (t = date.getUTCHours(), t < 10 ? '0' : '') + t + ':' +
      (t = date.getUTCMinutes(), t < 10 ? '0' : '') + t + ':' +
      (t = date.getUTCSeconds(), t < 10 ? '0' : '') + t + 'Z'
    );
  }

  /**
   * The toolbar
   */
  var toolbar = function() {
    return [
    dropdown('headline', 'Überschrift', [
        item('=', 'Überschrift Stufe 1'),
        item('==', 'Überschrift Stufe 2'),
        item('===', 'Überschrift Stufe 3'),
        item('====', 'Überschrift Stufe 4'),
        item('=====', 'Überschrift Stufe 5')
      ],
      function(evt) {
        var delim = evt.target.value;
        if (delim.length > 0)
          this.insertTag(delim + ' %s ' + delim + '\n', 'Überschrift');
        evt.target.selectedIndex = 0;
    }, ['wiki']),
    button('bold', 'Fetter Text', insert("'''%s'''"),
           ['wiki', 'forum', 'small']),
    button('italic', 'Kursiver Text', insert("''%s''"),
           ['wiki', 'forum', 'small']),
    button('underlined', 'Unterstrichener Text', insert('__%s__'),
           ['wiki', 'forum', 'small']),
    button('stroke', 'Durchgeschtrichener Text', insert('--(%s)--'),
           ['wiki', 'forum']),
    button('code', 'Code', insert("``%s``"),
           ['wiki', 'forum', 'small']),
    button('pre', 'Codeblock', insert('{{{\n%s\n}}}', 'Code'),
           ['wiki', 'forum']),
    button('wiki-link', 'Wiki Link', insert('[:%s:]', 'Seitenname'),
           ['wiki', 'forum']),
    button('external-link', 'Externer Link', insert('[%s]',
           'http://www.example.org/'), ['wiki', 'forum', 'small']),
    button('quote', 'Auswahl zitieren', function(evt) {
      var selection = this.getSelection();
      if (selection.length) {
        var lines = [];
        $.each(selection.split(/\r?\n/), function() {
          lines.push('>' + (this.charAt(0) != '>' ? ' ' : '') + this);
        });
        this.setSelection(lines.join('\n') + '\n');
      }
    }, ['wiki', 'forum']),
    button('picture', 'Bild', insert('[[Bild(%s)]]', 'Bildname'),
           ['wiki', 'forum']),
    (function(editor) {
      if (editor.profile != 'forum')
        return;
      var result = $('<div />');
      button('color', 'Farbe', function(evt) {
        colorbox.slideToggle('fast');
        return false;
      })(editor).appendTo(result);
      var colorbox = $('<ul class="colorbox" />').appendTo(result).hide();
      $.each(COLORS, function() {
        var color = this;
        $('<li />')
          .css('background-color', color)
          .click(function() {
            editor.insertTag('[color=' + color + ']%s[/color]', 'Eingefärbter Text');
          })
          .appendTo(colorbox);
      });
      $(document).click(function() {
        if (colorbox.is(':visible'))
          colorbox.slideUp('fast');
      });
      return result;
    }),
    (function(editor) {
      if (editor.profile != 'forum')
        return;
      var result = $('<div />');
      button('smilies', 'Smilies', function(evt) {
        smileybox.slideToggle('fast');
        return false;
      })(editor).appendTo(result);
      var smileybox = $('<ul class="smileybox" />').appendTo(result).hide();
      $.getJSON('/?__service__=wiki.get_smilies', function(smilies) {
        $.each(smilies, function() {
          var code = this[0], src = this[1];
          $('<li />')
            .append($('<img />')
              .attr('src', src)
              .attr('alt', code)
              .click(function() {
                editor.insertText(' ' + code + ' ');
              }))
            .appendTo(smileybox);
        });
      });
      $(document).click(function() {
        if (smileybox.is(':visible'))
          smileybox.slideUp('fast');
      });
      return result;
    }),
    button('date', 'Datum', function(evt) {
      this.insertTag('[[Datum(%s)]]', formatISO8601(new Date()));
    }, ['wiki']),
    button('sig', 'Signatur', function(evt) {
      this.insertText(' --- ' + (this.username ?
        '[user:' + this.username.replace(':', '::') + ':], ' : '') +
        '[[Datum(' + formatISO8601(new Date()) + ')]]');
    }, ['wiki']),
    dropdown('macro', 'Makro', [
        item('[[FehlendeSeiten(%s)]]', 'Fehlende Seiten'),
        item('[[TagListe(%s)]]', 'Tag-Liste'),
        item('[[Anhänge(%s)]]', 'Anhänge'),
        item('[[Seitenzahl(%s)]]', 'Seitenzahl'),
        item('[[Inhaltsverzeichnis(%s)]]', 'Inhaltsverzeichnis'),
        item('[[Einbinden(%s)]]', 'Seite einbinden'),
        item('[[Seitenliste(%s)]]', 'Seitenliste'),
        item('[[Seitenname(%s)]]', 'Aktueller Seitenname'),
        item('[[Weiterleitungen(%s)]]', 'Weiterleitungen'),
        item('[[ÄhnlicheSeiten(%s)]]', 'Ähnliche Seiten'),
        item('[[TagWolke(%s)]]', 'Tag-Wolke'),
        item('[[LetzteÄnderungen(%s)]]', 'Letzte Änderungen'),
        item('[[VerwaisteSeiten(%s)]]', 'Verwaiste Seiten'),
        item('[[NeueSeiten(%s)]]', 'Neue Seiten'),
      ],
      function(evt) {
        if (evt.target.value.length > 0)
          this.insertTag(evt.target.value, '');
        evt.target.selectedIndex = 0;
    }, ['wiki']),
    button('shrink', 'Verkleinern', function(evt) {
      if (this.textarea[0].rows >= 6)
        this.textarea[0].rows -= 3;
      else
        this.textarea[0].rows = 3;
      this.textarea[0].focus();
    }),
    button('enlarge', 'Vergrößern', function(evt) {
      if (isNaN(this.textarea[0].rows) || this.textarea[0].rows < .5)
        this.textarea[0].rows = 6;
      else
        this.textarea[0].rows += 3;
      this.textarea[0].focus();
    })
  ]};


  /**
   * Represents the wiki editor.  It's created with a jQuery object
   * or expression for the textarea.
   */
  WikiEditor = function(editor, profile) {
    var self = this, t;
    this.profile = profile || 'small';
    this.username = $CURRENT_USER || 'Anonymous';
    this.smilies = null;

    this.textarea = $(editor);
    /* XXX: disabled for the time being as it causes too much trouble
      .keypress(function(evt) {
        self.onKeyDown(evt);
      });*/

    /* create toolbar based on button layout */
    t = $('<ul class="toolbar" />').prependTo(this.textarea.parent());
    var bar = toolbar();
    for (var i = 0, n = bar.length, x; i != n; ++i)
      if (x = bar[i](self))
        x.appendTo($('<li />').appendTo(t))
  };

  /**
   * This method is called whenever a user presses a key.
   */
  WikiEditor.prototype.onKeyDown = function(evt) {
    /* on newline continue the current list or keep the indentation */
    if (evt.keyCode == 13) {
      var match = this.getCurrentLine()
                      .match(/^(\s*(?:\*|- |[01aAiI]\.)?\s*)(.*?)$/);
      if (match[1].length) {
        evt.preventDefault();
        /* continue indention / list */
        if (match[2].length)
          this.insertText('\n' + match[1]);
        /* or remove current list item too */
        else
          this.setCurrentLine('\n');
      }
    }
    /* on tab indent to a multiple of INDENTATION
       TODO: indent selected lines.
       TODO: ignore if shift+tab
       FIXME: how can a user without mouse navigate? */
    else if (evt.keyCode == 9) {
      evt.preventDefault();
      var pos = this.getCurrentLine().length;
      var indent = (Math.floor(pos / INDENTATION) + 1) * INDENTATION;
      for (var s = ''; pos < indent && (s += ' '); ++pos);
      this.insertText(s);
    }
  };

  /**
   * Insert a tag around a selection.  (Or if no value is selected then it
   * inserts a default text and marks it).  This does not use the
   * `getSelection` and `setSelection` for performance reasons.
   */
  WikiEditor.prototype.insertTag = function(format, def) {
    var
      t = this.textarea[0],
      args = (format instanceof Array) ? format : format.split('%s', 2);

    var
      before = args[0] || '',
      after = args[1] || '';

    if (typeof t.selectionStart != 'undefined') {
      var
        start = t.selectionStart,
        end = t.selectionEnd;
      var
        s1 = t.value.substring(0, start),
        s2 = t.value.substring(start, end),
        s3 = t.value.substring(end);

      s2 = (end != start) ? before + s2 + after : before + def + after;
      t.value = s1 + s2 + s3;
      t.focus();
      t.selectionStart = start + before.length;
      t.selectionEnd = start + (s2.length - after.length);
    }
    else if (typeof document.selection != 'undefined') {
      t.focus();
      var range = document.selection.createRange();
      var text = range.text;
      range.text = before + (text.length > 0 ? text : def) + after;
    }
  };

  /**
   * Get the currently selected text.
   */
  WikiEditor.prototype.getSelection = function() {
    var t = this.textarea[0];
    if (typeof t.selectionStart != 'undefined') {
      var
        start = t.selectionStart,
        end = t.selectionEnd;
      return (start == end) ? '' : t.value.substring(start, end);
    }
    else if (typeof document.selection != 'undefined') {
      var range = document.selection.createRange();
      return range.text;
    }
  };

  /**
   * Replace the current selection with a new text.
   */
  WikiEditor.prototype.setSelection = function(text, reselect) {
    var t = this.textarea[0];
    if (typeof t.selectionStart != 'undefined') {
      var
        start = t.selectionStart,
        end = t.selectionEnd;
      var
        s1 = t.value.substring(0, start),
        s2 = t.value.substring(end);

      t.value = s1 + text + s2;
      t.focus();
      if (reselect) {
        t.selectionStart = start + before.length;
        t.selectionEnd = start + text.length;
      }
      else
        t.selectionEnd = t.selectionStart = start + text.length;
    }
    else if (typeof document.selection != 'undefined') {
      t.focus();
      var range = document.selection.createRange();
      range.text = text;
      /* BUG: reselect? */
    }
  };

  /**
   * Insert text at the cursor position.  This works pretty much like
   * `setSelection` just that it deselects first.
   */
  WikiEditor.prototype.insertText = function(text) {
    var t = this.textarea[0];
    if (typeof t.selectionStart != 'undefined') {
      t.selectionStart = t.selectionEnd;
    }
    this.setSelection(text);
  };

  /**
   * Get the current line as string.
   */
  WikiEditor.prototype.getCurrentLine = function() {
    var t = this.textarea[0], i, c;
    if (typeof t.selectionStart != 'undefined') {
      var buffer = [];
      for (i = t.selectionEnd - 1; (c = t.value.charAt(i)) != '\n' && c; i--)
        buffer.push(c);
      buffer.reverse();
      for (i = t.selectionEnd; (c = t.value.charAt(i)) != '\n' && c; i++)
        buffer.push(c);
      return buffer.join('');
    }
    // XXX: IE-Version
    return '';
  };

  /**
   * Set the current line to a new value.
   */
  WikiEditor.prototype.setCurrentLine = function(text) {
    var t = this.textarea[0];
    if (typeof t.selectionStart != 'undefined') {
      var start, end, c;
      for (start = t.selectionEnd - 1;
           (c = t.value.charAt(start)) != '\n' && c;
           start--);
      for (end = t.selectionEnd;
           (c = t.value.charAt(end)) != '\n' && c;
           end++);
      t.value = t.value.substring(0, start) + text + t.value.substring(end);
      t.selectionStart = t.selectionEnd = start + text.length;
    }
    // XXX: IE-Version
  };

})();
