(function() {
  var mapping = {}

  PrivilegeBox = function(container, forums, privileges) {
    var self = this;
    this.container = $(container);
    var select = $('<select size="10" class="forums"></select>')
      .change(function() {
        $('.forum_privileges').hide();
        var id = '#forum_privileges-' + $(this).val();
        if($(id).length == 1) {
          $(id).show()
        } else {
          var privileges_select = $('<select multiple="multiple" class="forum_privileges" size="10"></select>')
            .attr('id', id.slice(1))
            .attr('name', id.slice(1))
            .change(function() {
              mapping[$(select.find(':selected')[0]).val()] = $(this).find(':selected');
            });
          $.each(privileges, function(i, perm) {
            privileges_select.append($('<option></option>').val(perm[0]).text(perm[1]));
          });
          privileges_select.val(mapping[$(this).val()]);
          self.container.append(privileges_select);
        };
      });
    $.each(forums, function(i, forum) {
      var [slug, name, perms] = forum;
      mapping[slug] = perms;
      select.append($('<option></option>').val(slug).text(name));
    });
    this.container.html('');
    this.container.append(select);
  }
})()
