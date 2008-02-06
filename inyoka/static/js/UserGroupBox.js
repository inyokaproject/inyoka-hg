/*
 *    js/UserGroupBox
 *    ~~~~~~~~~~~~~~~
 *
 *    A little box to add/remove the user to some groups.
 *
 *
 *    :copyright: 2008 by Christopher Grebs.
 *    :license: GNU GPL.
 */

(function() {

  GroupBox = function(container, user_joined, user_not_joined) {
    var self = this;
    this.container = $(container);

    // Groups the user not joined
    this.user_not_joined = $('select[@name="user_groups_not_joined"]');
    
    // Groups the user joined
    this.user_joined = $('select[@name="user_groups_joined"]')

    // add items to the select boxes
    this.rebuildBoxes(user_joined, user_not_joined);
  
    // add needed submit event 
    $($(container).find('input[@type="submit"]')[0])
      .click(function() {
        $.each([self.user_not_joined, self.user_joined], function() {
          this.find('option').each(function() {
            this.selected = true;
          });
        });
        return true;
      });
    
    // inject add/remove images
    $('<img src="' + $STATIC_URL + 'img/admin/add_item.png" />')
      .attr('alt', 'Gruppe hinzufügen')
      .attr('class', 'item_add')
      .insertAfter(this.user_not_joined)
      .click(function() {
        self.move(self.user_not_joined, self.user_joined);
      })
    $('<img src="' + $STATIC_URL + 'img/admin/remove_item.png" />')
      .attr('alt', 'Gruppe entfernen')
      .attr('class', 'item_remove')
      .insertBefore(this.user_joined)
      .click(function() {
        self.move(self.user_joined, self.user_not_joined);
      });
  }

  GroupBox.prototype = {
    rebuildBoxes: function(joined, not_joined) {
      var self = this;
      $.each(joined, function(i, group) {
        $('<option />').text(group).appendTo(self.user_joined);
      });

      $.each(not_joined, function(i, group) {
        $('<option />').text(group).appendTo(self.user_not_joined);
      });
    },
    move: function(from, to) {
      from.find('option:selected').each(function() {
        if (this.selected) {
          this.selected = false;
          $(this).appendTo(to);
            //XXX: why is the option moved to the `to` opject?
            //options[i] = null;
          }
      });
    },
  }
})()
