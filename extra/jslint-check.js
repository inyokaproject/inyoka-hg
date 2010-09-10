// Taken from jQuery source directory, modified for our
// needs. - Christopher Grebs.

load("extra/jslint.js");

var files = ["DateTime.js", "FeedSelector.js", "forum.js", "GMarkerManager.js",
             "ikhaya.js", "jquery.autocomplete.js", "jquery.cookie.js",
             "jquery.extensions.js", "jquery.tokenfield.js", "jquery.visualize.js",
             "NewTopic.js", "overall.js", "Pastebin.js", "PrivilegeBox.js",
             "UserGroupBox.js", "UserMap.js", "WikiEditor.js"]

for (var file in files) {
  var src = readFile("inyoka/static/js/" + files[file]);
  print( "check " + files[file] + " with jslint");

  JSLINT(src, { evil: true, forin: true, maxerr: 100 });

  // All of the following are known issues that we think are 'ok'
  // (in contradiction with JSLint) more information here:
  // http://docs.jquery.com/JQuery_Core_Style_Guidelines
  var ok = {
    "Expected an identifier and instead saw 'undefined' (a reserved word).": true,
    "Use '===' to compare with 'null'.": true,
    "Use '!==' to compare with 'null'.": true,
    "Expected an assignment or function call and instead saw an expression.": true,
    "Expected a 'break' statement before 'case'.": true
  };

  var e = JSLINT.errors, found = 0, w;

  for ( var i = 0; i < e.length; i++ ) {
    w = e[i];

    if ( !ok[ w.reason ] && (w.reason.indexOf("Expected '{' and instead saw"))) {
      found++;
      print( "\n" + w.evidence + "\n" );
      print( "    Problem at line " + w.line + " character " + w.character + ": " + w.reason );
    }
  }

  if ( found > 0 ) {
    print( "\n" + found + " Error(s) found." );

  } else {
    print( "JSLint check passed." );
  }
}
