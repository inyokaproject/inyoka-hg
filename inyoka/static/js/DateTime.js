/**
 * js.DateTime
 * ~~~~~~~~~~~
 *
 * This replaces a DateTime text field with a nice user-friendly gui including
 * a calendar and a table to select the clock.
 * It's based on django code that implements a similar widget for the admin
 * panel.
 *
 * :copyright: 2007 by Benjamin Wiegand, Django Project.
 * :license: GNU GPL.
 */

/* create a closure for all of our stuff so that we don't export the
   helper functions and variables.  The only thing that is defined as
   a global is the `DateTimeEditor`. */

(function() {
  var months = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
  var days_of_week = ['S', 'M', 'D', 'M', 'D', 'F', 'S'];

  function IsLeapYear(year) {
    return (((year % 4) == 0) && ((year % 100) != 0) || ((year % 400) == 0));
  }

  function getDaysInMonth(month, year) {
    var days;
    if ($.inArray(month, [1, 3, 5, 7, 8, 10, 12]) != -1) {
      days = 31;
    } else if ($.inArray(month, [4, 6, 9, 11]) != -1) {
      days = 30;
    } else if (month == 2 && IsLeapYear(year)) {
      days = 29;
    } else {
      days = 28;
    }
    return days;
  }

  DateTimeField = function(editor) {
    var self = this;
    this.input = $(editor).hide();
    this.readDateTime();
    this.calendarMonth = this.currentMonth;
    this.calendarYear = this.currentYear;
    this.container = $('<table class="datetime"></table>');
    var row = $('<tr></tr>').appendTo(this.container);
    this.calendar = $('<td></td>').appendTo(row);
    this.timetable = $('<td></td>').appendTo(row);
    this.drawCalendar();
    this.drawTimetable();
    this.input.parent().append(this.container);
  }

  DateTimeField.prototype = {
    readDateTime: function() {
      var dateTimeRegex = /(\d{4})-(\d{1,2})-(\d{1,2}) (\d{2}):(\d{2}):(\d{2})/
      dateTimeRegex.exec(this.input.val())
      var today = new Date();
      this.currentYear = RegExp.$1 || today.getFullYear();
      this.currentMonth = RegExp.$2 || today.getMonth() + 1;
      this.currentDay = RegExp.$3 || today.getDate();
      this.currentTime = [RegExp.$4 || today.getHours(), RegExp.$5 || today.getMinutes(),
                          RegExp.$6 || today.getSeconds()].join(':');
    },
    writeDateTime: function() {
      this.input.val(this.currentYear + '-' + this.currentMonth + '-' + this.currentDay + ' ' +
                     this.currentTime)
    },
    toggle: function() {
      this.container.toggle();
    },
    drawTimetable: function() {
      var self = this;
      var timetable = $('<table class="timetable"></table>').append(
        $('<tr><th class="caption">Uhrzeit</th></tr>')
      );
      this.timetable.append(timetable);
      var now = new Date();
      var times = [
        ['Jetzt', [now.getHours(), now.getMinutes(), now.getSeconds()].join(':')],
        ['Mitternacht', '00:00:00'],
        ['6 Uhr', '06:00:00'],
        ['Mittag', '12:00:00'],
        ['18 Uhr', '18:00:00']
      ];
      $.each(times, function(i, time) {
        timetable.append($('<tr></tr>').append($('<td></td>').append(
          $('<a></a>').text(time[0]).click(function() {
            self.currentTime = time[1];
            self.timeField.val(time[1]);
            self.writeDateTime();
          })
        )));
      })
      var col = $('<td></td>').appendTo($('<tr></tr>').appendTo(timetable));
      this.timeField = $('<input type="text"></input>')
        .appendTo(col)
        .val(this.currentTime)
        .change(function() {
          self.currentTime = self.timeField.val();
          self.writeDateTime();
        });
    },
    drawCalendar: function() {
      var self = this;
      var month = parseInt(this.calendarMonth);
      var year = parseInt(this.calendarYear);
      this.calendar.children().remove();
      var calendar = $('<table class="calendar"></table>').append(
        $('<tr></tr>').append(
          $('<th colspan="7" class="caption"></th>').append(
            $('<a class="calendarnav-next"></a>').text('>').click(function() {
              self.drawNextMonth()
            }),
            $('<a class="calendarnav-previous"></a>').text('<').click(function() {
              self.drawPreviousMonth()
            }),
            $('<span>' + months[month-1] + ' ' + year + '</span>').click(function() {
              $(this).hide().after(
                $('<input type="text" />')
                  .val(month + '-' + year)
                  .change(function() {
                    var dayRegex = /(\d{1,2})-(\d{1,2})-(\d+)/
                    dayRegex.exec($(this).val())
                    if (RegExp.$1) {
                      self.drawDate(RegExp.$3, RegExp.$2, RegExp.$1);
                    } else {
                      var monthRegex = /(\d{1,2})-(\d+)/
                      monthRegex.exec($(this).val())
                      if (RegExp.$1) {
                        self.drawDate(RegExp.$2, RegExp.$1);
                      }
                    }
                  })
                  .keypress(function(evt) {
                    if (evt.keyCode == 13) {
                      $(this).change();
                      return false;
                    }
                  })
              );
              $(this).next().focus();
            })
          )
        )
      );
      var tbody = $('<tbody></tbody>').appendTo(calendar);
      var row = $('<tr></tr>').appendTo(tbody);

      // draw days-of-week header
      $.each(days_of_week, function(i, d) {
        row.append($('<th class="weekday"></th>').text(d));
      })

      var starting_pos = new Date(year, month-1, 1).getDay();
      var days = getDaysInMonth(month, year);

      // Draw blanks before first of month
      var row = $('<tr></tr>').appendTo(tbody);
      for (var i = 0; i < starting_pos; i++) {
        $('<td style="background-color: #f3f3f3;"></td>').appendTo(row);
      }

      // Draw days of month
      var currentDay = 1;
      for (var i = starting_pos; currentDay <= days; i++) {
        if (i % 7 == 0 && currentDay != 1) {
          row = $('<tr></tr>').appendTo(tbody);
        }
        var td = $('<td></td>').append(
          $('<a></a>').text(currentDay).click(function() {
            $('.selected', $(this).parent().parent().parent()).removeClass('selected');
            $(this).parent().addClass('selected');
            self.currentDay = $(this).text();
            self.currentMonth = month;
            self.currentYear = year;
            self.writeDateTime();
          })
        ).appendTo(row);
        if (year == this.currentYear && month == this.currentMonth && currentDay == this.currentDay) {
          td.addClass('selected');
        }
        currentDay++;
      }

      // Draw blanks after end of month (optional, but makes code valid)
      while (row.children().length < 7) {
        row.append($('<td class="nonday"></td>'));
      }

      this.calendar.append(calendar);
    },
    drawDate: function(year, month, day) {
      day = parseInt(day);
      month = parseInt(month);
      year = parseInt(year);
      if (month > 0 && month < 13) { 
        this.calendarMonth = month;
        this.calendarYear = year;
        if (day) {
          this.currentDay = day;
          this.currentMonth = month;
          this.currentYear = year;
        }
        this.drawCalendar();
      }
    },
    drawPreviousMonth: function() {
      if (this.calendarMonth == 1) {
        this.calendarMonth = 12;
        this.calendarYear--;
      } else {
        this.calendarMonth--;
      }
      this.drawCalendar();
    },
    drawNextMonth: function() {
      if (this.calendarMonth == 12) {
        this.calendarMonth = 1;
        this.calendarYear++;
      } else {
        this.calendarMonth++;
      }
      this.drawCalendar();
    },
    drawPreviousYear: function() {
      this.calendarYear--;
      this.drawCalendar();
    },
    drawNextYear: function() {
      this.calendarYear++;
      this.drawCalendar();
    },
    destroy: function() {
      this.container.remove();
      this.input.show();
    }
  }
})()
