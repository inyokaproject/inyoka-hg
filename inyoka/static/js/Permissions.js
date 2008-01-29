(function() {
  var mapping = {}

  PermissionBox = function(container, forums, permissions) {
    var self = this;
    this.container = $(container);
    var select = $('<select size="10" class="forums"></select>')
      .change(function() {
        $('.permissions').hide();
        var id = '#permissions-' + $(this).val();
        if($(id).length == 1) {
          $(id).show()
        } else {
          var select = $('<select multiple="multiple" class="permissions" size="10"></select>')
            .attr('id', id.slice(1))
            .attr('name', id.slice(1));
          $.each(permissions, function(i, perm) {
            select.append($('<option></option>').val(perm[0]).text(perm[1]));
          });
          console.log(mapping, $(this).val());
          select.val(mapping[$(this).val()]);
          self.container.append(select);
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
