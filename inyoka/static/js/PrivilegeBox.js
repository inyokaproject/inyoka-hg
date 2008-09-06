(function() {
  var mapping = {}

  PrivilegeBox = function(container, forums, privileges) {
    var self = this;
    this.container = $(container);
    var select = $('<select size="15" class="forums"></select>')
      .change(function() {
        $('.forum_privileges').hide();
        var id = '#forum_privileges-' + $(this).val();
        if ($(id).length == 1) {
          $(id).show()
        } else {
          var privileges_select = $('<select multiple="multiple" class="forum_privileges" size="15"></select>')
            .attr('id', id.slice(1))
            .attr('name', id.slice(1))
          $.each(privileges, function(i, perm) {
            privileges_select.append($('<option></option>').val(perm[0]).text(perm[1]));
          });
          privileges_select.val(mapping[$(this).val()]);
          self.container.append(privileges_select);
        };
      });
    $.each(forums, function(i, forum) {
      var id, name, perms;
      id = forum[0];
      name = forum[1];
      perms = forum[2];
      mapping[id] = perms;
      select.append($('<option></option>').val(id).text(name));
    });
    this.container.html('');
    this.container.append(select);
  }
})()
