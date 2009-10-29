(function() {
  PrivilegeBox = function(container, forums, privileges) {
    var mapping = {}
    var selected_forums = [];
    this.container = $(container);
    var self = this;
    var list = $('<ul class="forums" />');
    $.each(forums, function(i, forum) {
      var id = forum[0];
      var name = forum[1];
      var positive = forum[2];
      var negative = forum[3];;
      mapping[id] = positive.concat($.map(negative, function(o) { return o * -1}));
      var li = $('<li />').text(name).attr('id', 'forum_' + id)
      if (positive != '' || negative != '') {
        li.css('color', 'red');
      };
      list.append(li.click(function(evt) {
        var id = $(this).attr('id').split('_')[1];
        if (evt.ctrlKey) {
          var pos = $.inArray(id, selected_forums);
          if (pos > -1 && selected_forums.length > 1) {
            selected_forums.splice(pos, 1);
          }
          if (pos == -1) {
            selected_forums.push(id);
          }
        } else {
          selected_forums = [id];
        }
        $(this).parent().children().removeClass('active');
        $.each(selected_forums, function(i, forum) {
          $('#forum_' + forum).addClass('active');
        });
        if (selected_forums.length == 1) {
          var forum = selected_forums[0];
          headline.text($('#forum_' + forum).text());
          $.each(privileges, function(id, name) {
            id = parseInt(id);
            if ($.inArray(id, mapping[forum]) > -1) s = '1'
            else if ($.inArray(id * -1, mapping[forum]) > -1) s = '-1'
            else s = '0';
            $('#priv_' + id + '_' + s).attr('checked', 'checked');
          });
        } else {
          headline.text(selected_forums.length + ' Foren');
          $('input[type=radio]', self.container).attr('checked', '');
        }
      }));
    });
    this.container.html('');
    this.container.append(list);
    var content = $('<div class="privileges"></div>').appendTo(this.container);
    var headline = $('<h5 />').appendTo(content);
    var priv_list = $('<dl />').appendTo(content);
    $.each(privileges, function(id, name) {
      var radio = function(val, text) {
        return $('<input type="radio" />').attr({
          name: 'priv_' + id,
          value: val,
          id: 'priv_' + id + '_' + val
        }).change(function() {
          var id = $(this).attr('name').split('_')[1];
          var val = $(this).val();
          $.each(selected_forums, function(i, forum_id) {
            var name = 'forum_privileges_' + forum_id;
            var result = $('input[name=' + name + ']');
            if (result.length == 0) {
              result = $('<input type="hidden" />').attr('name', name).appendTo(self.container);
              var s = mapping[forum_id];
            } else {
              var s = $.map(result.val().split(','), function(o) { return parseInt(o); });
            }
            function del(o, a) {
              if ($.inArray(o, a) > -1) { a.splice($.inArray(o, a), 1) };
            }
            del(id, s);
            del(id * -1, s);
            if (val != 0) {
              s.push(id * val);
            }
            result.val(s.join(','));
          });
        }).add(
          $('<label />').attr('for', 'priv_' + id + '_' + val).text(text)
        );
      };
      priv_list.append($('<dt />').text(name),
        $('<dd />').append(
          radio(1, 'Ja'), radio(0, 'Nicht gesetzt'), radio(-1, 'Nein')
        )
      );
    });
    $(list.children()[0]).click();
    content.append('<span class="note">Halte die Steuerungs-Taste gedrückt, um mehrere Foren auszuwählen.</span>')
  }
})()
