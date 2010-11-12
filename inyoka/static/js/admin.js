/**
 * js.admin
 * ~~~~~~~~
 *
 * Some scripts for the admin (requires jQuery).
 *
 * :copyright: (c) 2010 by the Inyoka Team, see AUTHORS for more details.
 * :license: GNU GPL, see LICENSE for more details.
 */

$(document).ready(function() {
  (function() {
    // create a WikiEditor instance for all signature fields
    var signature = new WikiEditor('textarea[name="signature"]');

    // Small helper to define a users group title
    $('input[name="group_titles"]').change(function() {
      var value = "";
      $('input[name="group_titles"]:checked').each(function(i) {
        if (i>0) value += " & ";
        value += $(this).val();
      });
      $('#id_member_title').val(value);
    });
  })();

});
