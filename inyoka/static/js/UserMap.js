/**
 * js.UserMap
 * ~~~~~~~~~~
 *
 * Display a google maps usermap.
 *
 * :copyright: 2007 by Armin Ronacher.
 * :license: GNU GPL.
 */

$(document).ready(function() {
  if (GBrowserIsCompatible()) {
    var map = new GMap2($('div.usermap')[0]);
    map.setCenter(new GLatLng(48, 12), 5);
    map.setMapType(G_SATELLITE_MAP);
    map.addControl(new GLargeMapControl());
    map.addControl(new GMapTypeControl());

    var userIcon = new GIcon();
    userIcon.image = $STATIC_URL + 'img/map_user_marker.png';
    userIcon.iconSize = new GSize(24, 24);
    userIcon.iconAnchor = new GPoint(6, 20);
    userIcon.infoWindowAnchor = new GPoint(5, 1);

    var markerManager = new GMarkerManager(map);
    $.getJSON('/?__service__=portal.get_usermap_markers', function(data) {
      var markers = [];
      function flushMarkers() {
        markerManager.addMarkers(markers, 8);
        markers = [];
      }
      $.each(data.markers, function() {
        var pos = new GLatLng(this.pos[0], this.pos[1]);
        if (this.type == 'user') {
          markers.push(new GMarker(pos, {
            title:    this.detail.username,
            icon:     userIcon
          }));
        }
        if (markers.length >= 100)
          flushMarkers();
      });
      flushMarkers();
      markerManager.refresh();
    });
  }
});

$(document).unload(function() {
  GUnload();
});
